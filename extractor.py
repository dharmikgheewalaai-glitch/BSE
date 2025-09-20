# extractor.py

import pdfplumber
import re
from io import BytesIO

# 🔹 Classification rules
HEAD_RULES = {
    "CASH": ["ATM", "CASH", "CSH", "CASA"],
    "Withdrawal": ["UPI", "IMPS", "NEFT", "TRANSFER", "WITHDRAWAL", "DEBIT"],
    "Interest": ["INT", "INTEREST", "CR INT"],
    "Charge": ["CHRG", "CHARGE", "FEE", "GST", "PENALTY"],
}

# 🔹 Bank-specific header mappings
HEADER_ALIASES = {
    "date": ["date", "txn date", "transaction date", "value date", "tran date"],
    "particulars": [
        "particulars",
        "description",
        "narration",
        "transaction particulars",
        "details",
        "remarks"
    ],
    "debit": [
        "debit",
        "withdrawal amt.",
        "withdrawal",
        "debit amount",
        "dr"
    ],
    "credit": [
        "credit",
        "deposit amt.",
        "deposit",
        "credit amount",
        "cr"
    ],
    "balance": [
        "balance",
        "running balance",
        "closing balance",
        "bal"
    ]
}

def normalize_header(header: str):
    """Map a header to a standard name (date, particulars, debit, credit, balance)."""
    header = header.strip().lower()
    for std, aliases in HEADER_ALIASES.items():
        if any(header.startswith(a) or a in header for a in aliases):
            return std
    return header

def classify_transaction(particulars: str) -> str:
    """Classify transaction based on Particulars/Description"""
    particulars = (particulars or "").upper()
    for head, keywords in HEAD_RULES.items():
        if any(k in particulars for k in keywords):
            return head
    return "Other"

def process_file(file_bytes, filename):
    """
    Extract metadata + transactions from PDF bank statements
    Supports SBI, HDFC, ICICI, Axis, Sutex Cooperative Bank
    """
    meta = {"account_number": None, "name": None, "bank": None}
    transactions = []

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            try:
                table = page.extract_table()
                if not table:
                    continue

                # Normalize headers
                headers = [normalize_header(h or "") for h in table[0]]
                for row in table[1:]:
                    row_dict = dict(zip(headers, row))

                    date = row_dict.get("date")
                    particulars = row_dict.get("particulars")
                    debit = row_dict.get("debit")
                    credit = row_dict.get("credit")
                    balance = row_dict.get("balance")

                    if not (date and particulars):
                        continue

                    # Parse amount
                    amount = None
                    if debit:
                        try:
                            amount = -float(debit.replace(",", ""))
                        except:
                            pass
                    elif credit:
                        try:
                            amount = float(credit.replace(",", ""))
                        except:
                            pass

                    if amount is None:
                        continue

                    head = classify_transaction(particulars)

                    transactions.append({
                        "Date": date.strip(),
                        "Particulars": particulars.strip(),
                        "Amount": amount,
                        "Head": head,
                        "Balance": balance.strip() if balance else None
                    })

            except Exception as e:
                print("Error extracting table:", e)
                continue

    return meta, transactions
