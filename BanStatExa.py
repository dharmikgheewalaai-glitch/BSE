# extractor.py
import re
import io
from datetime import datetime
from pathlib import Path

# try optional libs
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_bytes
except Exception:
    convert_from_bytes = None

# ---------- Configuration ----------
CATEGORY_MAP = {
    "CASH": ["ATM", "CSH", "CASH", "CASA"],
    "Withdrawal": ["UPI", "IMPS"],
    "Transfer": ["NEFT", "RTGS"],
    "Salary": ["SALARY", "PAYROLL"],
    "Interest": ["INT", "INTEREST"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST"],
    "Refund": ["REV", "REFUND"],
    "Card Payment": ["POS", "DEBIT CARD"],
    "Credit Card": ["CREDIT CARD PAYMENT"],
    "Dividend": ["DIV", "DIVIDEND"]
}

DATE_PATTERNS = [
    r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b',
    r'\b(\d{2}[/-]\d{2}[/-]\d{2})\b',
    r'\b(\d{4}[/-]\d{2}[/-]\d{2})\b',
    r'\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b'
]

AMOUNT_RE = r'[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?'

# ---------- Helpers ----------
def normalize_amount(s):
    if not s:
        return None
    s = re.sub(r'[^\d\-,.\)]', '', s)
    neg = "(" in s and ")" in s
    s = s.replace("(", "").replace(")", "").replace(",", "").strip()
    try:
        val = float(s)
        return -val if neg else val
    except:
        return None

def try_parse_date(s):
    if not s:
        return None
    fmts = ['%d/%m/%Y','%d-%m-%Y','%d/%m/%y','%d-%m-%y','%Y-%m-%d','%d %b %Y','%d %B %Y']
    for f in fmts:
        try:
            return datetime.strptime(s.strip(), f).date().isoformat()
        except:
            pass
    # fallback: return raw if nothing parsed
    return None

def categorize_transaction(description: str) -> str:
    desc = (description or "").upper()
    for head, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in desc:
                return head
    return "Withdrawal"  # default per your rule

def extract_party_info(desc: str):
    if not desc:
        return None, None
    acc_match = re.search(r'\b\d{9,18}\b', desc)
    party_acc = acc_match.group(0) if acc_match else None

    # naive name extraction: text after TO / FROM or last token if it looks alphabetic
    name = None
    m = re.search(r'\b(?:TO|FROM)\b\s*(.+)$', desc, re.I)
    if m:
        candidate = m.group(1).strip()
        # strip any trailing digits or account numbers
        candidate = re.sub(r'\b\d{6,}\b', '', candidate).strip()
        name = candidate if candidate else None
    return party_acc, name

def extract_meta(text):
    meta = {}
    if not text:
        return meta
    acc = re.search(r'Account\s*No[:\s-]+(\d+)', text, re.I)
    name = re.search(r'Account\s*(?:Holder|Name)[:\s-]+([A-Za-z .,&-]+)', text, re.I)
    ifsc = re.search(r'IFSC[:\s-]+([A-Z]{4}0[A-Z0-9]{6})', text, re.I)
    branch = re.search(r'Branch[:\s-]+([A-Za-z0-9 ,.-]+)', text, re.I)
    period = re.search(r'(?:Statement\s*Period|From)\s*:?(.+?)To(.+)', text, re.I)

    if acc: meta["account_number"] = acc.group(1)
    if name: meta["account_holder"] = name.group(1).strip()
    if ifsc: meta["ifsc"] = ifsc.group(1)
    if branch: meta["branch"] = branch.group(1).strip()
    if period:
        meta["statement_period"] = f"{period.group(1).strip()} to {period.group(2).strip()}"
    return meta

def extract_from_text(text, page_no=0):
    txns = []
    if not text:
        return txns
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if any(re.search(p, ln) for p in DATE_PATTERNS) and re.search(AMOUNT_RE, ln):
            nums_raw = re.findall(AMOUNT_RE, ln)
            nums = [normalize_amount(n) for n in nums_raw]
            nums = [n for n in nums if n is not None]

            debit = credit = balance = None
            if len(nums) == 1:
                credit = nums[0]
            elif len(nums) == 2:
                debit, credit = nums
            elif len(nums) >= 3:
                debit, credit, balance = nums[-3], nums[-2], nums[-1]

            # date:
            date_token = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, ln)
                if m:
                    date_token = m.group(1)
                    break
            date_iso = try_parse_date(date_token) if date_token else None

            desc = re.sub(AMOUNT_RE, '', ln)
            desc = re.sub(r'\s{2,}', ' ', desc).strip()
            if not desc:
                desc = ln

            head = categorize_transaction(desc)
            party_acc, party_name = extract_party_info(desc)

            txns.append({
                "date": date_iso,
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "type": "Deposit" if credit and not debit else "Withdrawal",
                "head": head,
                "party_account": party_acc,
                "party_name": party_name,
                "source_page": page_no
            })
    return txns

# ---------- PDF / IMAGE handlers ----------
def extract_from_pdf_bytes(pdf_bytes):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber not available in environment.")
    meta = {}
    txns = []
    f = io.BytesIO(pdf_bytes)
    with pdfplumber.open(f) as pdf:
        # try text extraction first
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if i == 0:
                meta.update(extract_meta(text))
            page_txns = extract_from_text(text, page_no=i)
            txns.extend(page_txns)

    # if no transactions were found and OCR is available, try OCR fallback
    if not txns and convert_from_bytes and pytesseract:
        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            ocr_text = ""
            for i, img in enumerate(images):
                ocr_text += pytesseract.image_to_string(img) + "\n"
            if ocr_text.strip():
                if not meta:
                    meta.update(extract_meta(ocr_text))
                txns = extract_from_text(ocr_text)
        except Exception:
            # silently fallback: leave txns empty
            pass
    return meta, txns

def extract_from_image_bytes(img_bytes, filename=None):
    if Image is None:
        raise RuntimeError("Pillow not available in environment.")
    meta = {}
    txns = []
    f = io.BytesIO(img_bytes)
    try:
        img = Image.open(f)
        if pytesseract:
            text = pytesseract.image_to_string(img)
            meta.update(extract_meta(text))
            txns = extract_from_text(text)
        else:
            raise RuntimeError("pytesseract not available for image OCR.")
    except Exception as e:
        raise RuntimeError(f"Failed to process image: {e}")
    return meta, txns

# ---------- Public API ----------
def process_file(file_bytes, filename):
    """
    file_bytes: bytes of uploaded file
    filename: original filename (e.g., "SBI_Mar23.pdf")
    returns (meta_dict, transactions_list)
    """
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_from_pdf_bytes(file_bytes)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return extract_from_image_bytes(file_bytes, filename=filename)
    else:
        raise ValueError("Unsupported file type: " + ext)
