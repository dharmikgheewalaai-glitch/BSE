# extractor.py

import pdfplumber
import re
from io import BytesIO

# 🔹 Rules for categorizing transactions
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "TRANSFER", "WITHDRAWAL", "DEBIT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
}

def classify_transaction(description: str) -> str:
    """Return category based on description keywords"""
    description = description.upper()
    for head, keywords in HEAD_RULES.items():
        if any(k in description for k in keywords):
            return head
    return "Other"

def process_file(file_bytes, filename):
    """
    Extract metadata + transactions from a text-based PDF
    """
    meta = {"account_number": None, "name": None, "bank": None}
    transactions = []

    # ✅ Fix: wrap bytes in BytesIO so pdfplumber can read it
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    # 🔹 Try to extract account details
    acc_match = re.search(r"Account\s*No[:\- ]+(\d+)", text, re.I)
    name_match = re.search(r"Name[:\- ]+([A-Za-z ]+)", text, re.I)
    bank_match = re.search(r"(HDFC|SBI|ICICI|AXIS|KOTAK|PNB|BANK OF BARODA)", text, re.I)

    if acc_match:
        meta["account_number"] = acc_match.group(1)
    if name_match:
        meta["name"] = name_match.group(1).strip()
    if bank_match:
        meta["bank"] = bank_match.group(1)

    # 🔹 Extract transactions (simple parsing)
    lines = text.splitlines()
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 3:
            continue

        # Assume format: DATE DESCRIPTION AMOUNT BALANCE
        date = parts[0]
        if not re.match(r"\d{2}[-/]\d{2}[-/]\d{2,4}", date):
            continue  # not a transaction line

        description = " ".join(parts[1:-2])
        try:
            amount = float(parts[-2].replace(",", ""))
        except:
            continue

        head = classify_transaction(description)

        transactions.append({
            "Date": date,
            "Description": description,
            "Amount": amount,
            "Head": head
        })

    return meta, transactions
