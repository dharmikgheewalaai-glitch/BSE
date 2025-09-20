# Bank Statement Extractor (Streamlit)

Upload bank PDF or image, extract transactions + meta, download CSV/JSON.

## Run locally
1. pip install -r requirements.txt
2. Install Tesseract OCR (and poppler for pdf2image) if you want OCR for scanned PDFs:
   - Ubuntu: sudo apt install tesseract-ocr poppler-utils
   - macOS: brew install tesseract poppler
   - Windows: install Tesseract and add to PATH; install poppler for windows and set PDF2IMAGE path.
3. streamlit run app.py

## Deploy
Push to GitHub, then create a new app on Streamlit Cloud and point to this repo.

Notes: Streamlit Cloud cannot always install system-level packages (Tesseract/poppler). For scanned PDFs on cloud, use a cloud OCR service.
