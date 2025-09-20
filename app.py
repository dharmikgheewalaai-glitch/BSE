import streamlit as st
import pandas as pd
import json
from pathlib import Path
from extractor import process_file

st.set_page_config(page_title="Bank Statement Extractor", layout="wide")
st.title("🏦 Bank Statement Extractor")

uploaded = st.file_uploader("Upload a bank statement (PDF)", type=["pdf"])

if uploaded:
    file_bytes = uploaded.read()
    filename = uploaded.name

    try:
        with st.spinner("Processing..."):
            meta, txns = process_file(file_bytes, filename)
    except Exception as e:
        st.error(f"❌ Failed to process: {e}")
        st.stop()

    st.subheader("📌 Account Info")
    st.json(meta)

    st.subheader("📊 Transactions")
    if not txns:
        st.warning("No transactions found.")
    else:
        df = pd.DataFrame(txns)
        st.dataframe(df, use_container_width=True)

        base = Path(filename).stem
        csv_name = f"{base}_transactions.csv"
        json_name = f"{base}_transactions.json"

        st.download_button("⬇ Download CSV", df.to_csv(index=False).encode("utf-8"), file_name=csv_name, mime="text/csv")
        st.download_button("⬇ Download JSON", json.dumps({"meta": meta, "transactions": txns}, indent=2).encode("utf-8"), file_name=json_name, mime="application/json")
