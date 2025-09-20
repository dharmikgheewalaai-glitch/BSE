# app.py
import streamlit as st
import pandas as pd
from pathlib import Path
import json
from extractor import process_file

st.set_page_config(page_title="Bank Statement Extractor", layout="wide")
st.title("🏦 Bank Statement Extractor")

st.markdown("Upload a bank statement (PDF or image). The app will extract meta and transactions and let you download CSV/JSON.")

uploaded = st.file_uploader("Upload statement (pdf, jpg, png)", type=["pdf", "jpg", "jpeg", "png", "tiff", "bmp"])

if uploaded:
    file_bytes = uploaded.read()
    filename = uploaded.name
    try:
        with st.spinner("Processing..."):
            meta, txns = process_file(file_bytes, filename)
    except Exception as e:
        st.error(f"Processing failed: {e}")
        st.info("If this is an image-based PDF you may need Tesseract/poppler installed (works locally). For Streamlit Cloud, consider a cloud OCR provider.")
        st.stop()

    st.subheader("Meta")
    st.json(meta or {})

    st.subheader("Transactions")
    if not txns:
        st.warning("No transactions detected. Try a text-based PDF or run locally with Tesseract installed.")
    else:
        df = pd.DataFrame(txns)
        st.dataframe(df, use_container_width=True)

        base = Path(filename).stem
        csv_name = f"{base}_transactions.csv"
        json_name = f"{base}_transactions.json"

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        json_bytes = json.dumps({"meta": meta, "transactions": txns}, indent=2).encode("utf-8")

        st.download_button("⬇️ Download CSV", csv_bytes, file_name=csv_name, mime="text/csv")
        st.download_button("⬇️ Download JSON", json_bytes, file_name=json_name, mime="application/json")
