# Equation Converter (Word/PDF → Word with Native Equations)

A Streamlit app with **password login** that converts:
- **Word → Word**: DOCX containing LaTeX-like math (e.g., `([ ... ])`, `$...$`, `$$...$$`) into a DOCX with **native Word equations** (OMML) via Pandoc.
- **PDF → Word**: Best-effort conversion via Pandoc. (True equation recovery from arbitrary PDFs is not guaranteed.)

## Features
- Login required (password from environment variable `APP_PASSWORD`).
- Two tabs:
  - **Word → Word**: Converts LaTeX-like math to native equations.
  - **PDF → Word**: Uses Pandoc PDF reader (quality depends on the PDF source).
- Download the converted DOCX.

## How it works (Word → Word)
1. DOCX is parsed for text.
2. Custom blocks `([ ... ])` are normalized to `$$ ... $$` (display math).
3. Existing `$...$` and `$$...$$` are kept as-is.
4. Text is converted to Markdown and then to Word via **Pandoc** (which renders equations as OMML).

## Requirements
- Python 3.8+
- `pip install -r requirements.txt`
- **Pandoc** installed and on PATH (see https://pandoc.org/installing.html)

## Run locally
```bash
export APP_PASSWORD="your_password_here"
streamlit run app.py
```

On Windows PowerShell:
```powershell
$env:APP_PASSWORD="your_password_here"
streamlit run app.py
```

## Deploy to Streamlit Cloud / GitHub
1. Push these files to a GitHub repo.
2. In Streamlit Cloud, set a secret or environment variable `APP_PASSWORD`.
3. Deploy the app (entry point `app.py`).

## Notes on PDF → Word
- Converting arbitrary PDFs to **native** Word equations is fundamentally hard.
- The app uses Pandoc to extract text; equations will be improved **only if** the PDF has extractable math text or LaTeX-like patterns.
- For guaranteed fidelity, start from DOCX with LaTeX math or original LaTeX sources.
