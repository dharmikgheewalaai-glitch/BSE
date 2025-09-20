#!/usr/bin/env python3
"""
Bank Statement Extractor (Auto same file name)
- Extracts meta info + transactions
- Classifies into Type + Head
- Saves CSV/JSON with same file name
"""

import re
import sys
import json
import csv
from pathlib import Path
from datetime import datetime

import pdfplumber
from PIL import Image
import pytesseract

# ---------- CATEGORY MAP ----------
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

# ---------- HELPERS ----------
def normalize_amount(s):
    if not s:
        return None
    s = re.sub(r'[^\d\-,.\)]', '', s)
    neg = "(" in s and ")" in s
    s = s.replace("(", "").replace(")", "").replace(",", "")
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
    return None

def categorize_transaction(description: str) -> str:
    desc = description.upper()
    for head, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in desc:
                return head
    return "Withdrawal"  # default

def extract_party_info(desc: str):
    acc_match = re.search(r'\b\d{9,18}\b', desc)
    name_match = None
    if "TO" in desc.upper() or "FROM" in desc.upper():
        parts = desc.split()
        if len(parts) >= 3:
            name_match = parts[-1]
    return acc_match.group(0) if acc_match else None, name_match

# ---------- META ----------
def extract_meta(text):
    meta = {}
    acc = re.search(r'Account\s*No[:\s-]+(\d+)', text, re.I)
    name = re.search(r'Account\s*Holder[:\s-]+([A-Za-z ]+)', text, re.I)
    ifsc = re.search(r'IFSC[:\s-]+([A-Z]{4}0[A-Z0-9]{6})', text, re.I)
    branch = re.search(r'Branch[:\s-]+([A-Za-z ]+)', text, re.I)
    period = re.search(r'(?:Statement\s*Period|From)\s*:?(.+?)To(.+)', text, re.I)

    if acc: meta["account_number"] = acc.group(1)
    if name: meta["account_holder"] = name.group(1).strip()
    if ifsc: meta["ifsc"] = ifsc.group(1)
    if branch: meta["branch"] = branch.group(1).strip()
    if period: meta["statement_period"] = f"{period.group(1).strip()} to {period.group(2).strip()}"
    return meta

# ---------- TRANSACTIONS ----------
def extract_from_text(text, page_no=0):
    results = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        if any(re.search(p, ln) for p in DATE_PATTERNS) and re.search(AMOUNT_RE, ln):
            nums = [normalize_amount(n) for n in re.findall(AMOUNT_RE, ln)]
            nums = [n for n in nums if n is not None]
            debit = credit = balance = None
            if len(nums) == 1:
                credit = nums[0]
            elif len(nums) == 2:
                debit, credit = nums
            elif len(nums) >= 3:
                debit, credit, balance = nums[-3], nums[-2], nums[-1]

            date_match = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, ln)
                if m:
                    date_match = m.group(1)
                    break
            date_iso = try_parse_date(date_match) if date_match else None

            desc = re.sub(AMOUNT_RE, '', ln)
            desc = re.sub(r'\s{2,}', ' ', desc).strip()

            head = categorize_transaction(desc)
            party_acc, party_name = extract_party_info(desc)

            results.append({
                "date": date_iso,
                "description": desc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
                "type": "Deposit" if credit else "Withdrawal",
                "head": head,
                "party_account": party_acc,
                "party_name": party_name,
                "source_page": page_no
            })
    return results

# ---------- PDF / IMAGE ----------
def extract_from_pdf(path):
    out, meta = [], {}
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if i == 0:
                meta = extract_meta(text)
            out.extend(extract_from_text(text, page_no=i))
    return meta, out

def extract_from_image(path):
    img = Image.open(path)
    text = pytesseract.image_to_string(img)
    meta = extract_meta(text)
    txns = extract_from_text(text)
    return meta, txns

# ---------- SAVE ----------
def save_csv(meta, txns, inpath):
    outpath = Path(inpath).with_suffix('') .as_posix() + "_transactions.csv"
    keys = ["date","description","debit","credit","balance","type","head","party_account","party_name","source_page"]
    with open(outpath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in txns:
            writer.writerow(r)
    print(f"Wrote CSV: {outpath}")

def save_json(meta, txns, inpath):
    outpath = Path(inpath).with_suffix('') .as_posix() + "_transactions.json"
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump({"meta": meta, "transactions": txns}, f, ensure_ascii=False, indent=2)
    print(f"Wrote JSON: {outpath}")

# ---------- MAIN ----------
def main():
    if len(sys.argv) < 2:
        print("Usage: python bank_statement_extractor.py <file.pdf|file.jpg>")
        sys.exit(1)
    path = Path(sys.argv[1])

    if path.suffix.lower() == ".pdf":
        meta, txns = extract_from_pdf(path)
    else:
        meta, txns = extract_from_image(path)

    save_csv(meta, txns, path)
    save_json(meta, txns, path)
    print(f"Extracted {len(txns)} transactions")

if __name__ == "__main__":
    main()
