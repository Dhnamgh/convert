import os
import io
import re
import tempfile
import subprocess
import streamlit as st

from docx import Document

APP_TITLE = "Equation Converter (Word/PDF → Word with Native Equations)"
PASSWORD_ENV = "APP_PASSWORD"  # Set this in your deployment environment

# ----------------------- Authentication -----------------------
def login_view():
    st.title("🔐 Login")
    st.write("Enter password to access the converter.")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        real = os.environ.get(PASSWORD_ENV, "").strip()
        if not real:
            st.error("Server misconfiguration: APP_PASSWORD is not set.")
            return
        if pwd == real:
            st.session_state.authenticated = True
            st.experimental_rerun()
        else:
            st.error("Incorrect password.")

def logout_button():
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.experimental_rerun()

# ----------------------- Utilities ----------------------------
def normalize_quotes(s: str) -> str:
    return (s.replace('\xa0', ' ')
             .replace('–', '--')
             .replace('—', '---')
             .replace('“', '"').replace('”', '"')
             .replace("’", "'"))

def extract_text_from_docx(file_bytes: bytes) -> str:
    # Read docx and return plain text separated by blank lines
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        tmp_path = tmp.name
    try:
        doc = Document(tmp_path)
        parts = []
        for p in doc.paragraphs:
            txt = "".join(run.text for run in p.runs)
            parts.append(txt.strip())
        return "\n\n".join([normalize_quotes(p) for p in parts if p is not None])
    finally:
        try: os.remove(tmp_path)
        except: pass

def to_markdown_with_math(src_text: str) -> str:
    """
    Convert custom math markers to LaTeX math for Pandoc.
    - Block pattern: ([ ... ])  --> $$ ... $$
    - Keep $...$ and $$...$$ as-is.
    """
    s = src_text.replace("\r\n", "\n")
    pattern_block = re.compile(r"\(\[\s*(.*?)\s*\]\)", re.DOTALL)
    s = re.sub(pattern_block, lambda m: r"$$\n" + m.group(1).strip() + r"\n$$", s)
    # Ensure spacing around display math for Pandoc
    s = re.sub(r"\s*\$\$\s*\n", "\n\n$$\n", s)
    s = re.sub(r"\n\s*\$\$\s*", "\n$$\n\n", s)
    return s

def ensure_pandoc() -> str:
    try:
        out = subprocess.check_output(["pandoc", "--version"], stderr=subprocess.STDOUT, text=True)
        return out.splitlines()[0]
    except Exception as e:
        raise RuntimeError("Pandoc not found. Please install pandoc and ensure it is on PATH.")

def md_to_docx(md_text: str) -> bytes:
    ensure_pandoc()
    with tempfile.TemporaryDirectory() as td:
        md_path = os.path.join(td, "input.md")
        out_path = os.path.join(td, "output.docx")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        cmd = ["pandoc", md_path, "-o", out_path, "--from", "markdown+tex_math_dollars", "--to", "docx"]
        subprocess.check_call(cmd)
        with open(out_path, "rb") as f:
            return f.read()

def pdf_to_docx(pdf_bytes: bytes) -> bytes:
    """
    Best-effort PDF -> DOCX via Pandoc. Equations fidelity depends on PDF source.
    True native equation recovery is only guaranteed if PDF text contains LaTeX-like math or math text.
    """
    ensure_pandoc()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmpin:
        tmpin.write(pdf_bytes)
        tmpin.flush()
        in_path = tmpin.name
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmpout:
            out_path = tmpout.name
        cmd = ["pandoc", in_path, "-o", out_path]
        subprocess.check_call(cmd)
        with open(out_path, "rb") as f:
            data = f.read()
        try: os.remove(out_path)
        except: pass
        return data
    finally:
        try: os.remove(in_path)
        except: pass

# ----------------------- UI ----------------------------
def main_app():
    st.title(APP_TITLE)
    st.caption("Convert Word/PDF containing LaTeX-like math into Word with native equations.")

    tabs = st.tabs(["Word → Word", "PDF → Word"])

    with tabs[0]:
        st.subheader("DOCX (with LaTeX math code) → DOCX (native Word equations)")
        st.write("Supported math markers: `([ ... ])`, `$...$`, `$$...$$`.")

        up = st.file_uploader("Upload DOCX", type=["docx"], key="docx_up")
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Document Title (optional)", "")
        with col2:
            author = st.text_input("Author (optional)", "")

        if st.button("Convert Word → Word", type="primary") and up:
            try:
                raw = up.read()
                text = extract_text_from_docx(raw)
                md = to_markdown_with_math(text)

                # Prefix title/author if provided
                if title or author:
                    header = ""
                    if title:
                        header += f"# {title}\n\n"
                    if author:
                        header += f"**{author}**\n\n"
                    md = header + md

                out_bytes = md_to_docx(md)
                st.success("Conversion done.")
                st.download_button("Download DOCX", data=out_bytes, file_name="converted_equations.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.error(f"Error: {e}")

    with tabs[1]:
        st.subheader("PDF → DOCX (best-effort)")
        st.write("This uses Pandoc to extract text and convert to DOCX. Native equation recovery from arbitrary PDFs is **not guaranteed**.")
        up = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_up")

        if st.button("Convert PDF → Word") and up:
            try:
                pdf_bytes = up.read()
                out_bytes = pdf_to_docx(pdf_bytes)
                st.success("Conversion done.")
                st.download_button("Download DOCX", data=out_bytes, file_name="converted_from_pdf.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as e:
                st.error(f"Error: {e}")

st.set_page_config(page_title=APP_TITLE, page_icon="🧮", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_view()
else:
    logout_button()
    main_app()
