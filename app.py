# app.py
import streamlit as st
import pandas as pd
from extractor import process_file

st.title("📄 Bank Statement Extractor")

uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])

if uploaded_file is not None:
    st.info(f"Processing: {uploaded_file.name} ...")

    # Read file
    file_bytes = uploaded_file.read()

    # Call extractor
    meta, transactions = process_file(file_bytes, uploaded_file.name)

    if not transactions:
        st.error("⚠️ No transactions found. Try with another PDF or check if it's a scanned copy.")
    else:
        # Convert to DataFrame
        df = pd.DataFrame(transactions)

        st.success("✅ Transactions Extracted Successfully!")
        
        # Show metadata
        with st.expander("📌 Account Details"):
            st.json(meta)

        # Show DataFrame
        st.dataframe(df, use_container_width=True)

        # Allow CSV download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Extracted Transactions as CSV",
            data=csv,
            file_name="transactions.csv",
            mime="text/csv"
        )
