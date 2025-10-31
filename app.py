# app.py
import os
import re
import sys
import shutil
import tempfile
import subprocess
import streamlit as st
from docx import Document

APP_TITLE = "CONVERT FILE AND DATA"
PASSWORD_ENV = "APP_PASSWORD"  # set this env var to enable login

# Page config MUST be first UI call
st.set_page_config(page_title=APP_TITLE, page_icon="🧮", layout="wide")

# ---------- Sticky footer (center bottom) ----------
FOOTER_HTML = """
<style>
#custom-footer {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0.5rem;
  color: rgba(49, 51, 63, 0.6);
  font-size: 0.9rem;
  z-index: 1000;
}
</style>
<div id="custom-footer">bản quyền thuộc về <strong>TS DHN</strong></div>
"""
st.markdown(FOOTER_HTML, unsafe_allow_html=True)

# ---------- Auth ----------
def login_view():
    st.markdown(f"## {APP_TITLE}")
    st.write("---")
    st.title("🔐 Login")
    st.write("Nhập mật khẩu để truy cập ứng dụng.")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        real = os.environ.get(PASSWORD_ENV, "").strip()
        if not real:
            st.error("Server chưa cấu hình `APP_PASSWORD`. Vui lòng đặt biến môi trường trước khi chạy.")
            return
        if pwd == real:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Mật khẩu không đúng.")

def logout_button():
    st.sidebar.markdown("### 🔐 Session")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ---------- Pandoc handling ----------
def ensure_pandoc() -> str:
    """
    Ensure pandoc is available. Strategy:
    1) If 'pandoc' exists in PATH -> return its version line.
    2) Else try to download via pypandoc and make it available.
    3) If still not available, raise with clear manual instructions.
    """
    # 1) Try existing pandoc
    try:
        out = subprocess.check_output(["pandoc", "--version"], stderr=subprocess.STDOUT, text=True)
        return out.splitlines()[0]
    except Exception:
        pass

    # 2) Try pypandoc download
    try:
        import pypandoc
        pypandoc.download_pandoc()  # downloads and configures a local pandoc

        # After download, try again
        try:
            out = subprocess.check_output(["pandoc", "--version"], stderr=subprocess.STDOUT, text=True)
            return out.splitlines()[0]
        except Exception:
            # attempt to locate common bin dirs
            candidates = []
            home = os.path.expanduser("~")
            candidates += [os.path.join(home, ".local", "bin")]
            if hasattr(sys, "prefix"):
                candidates += [os.path.join(sys.prefix, "bin")]
            for b in [p for p in candidates if p and os.path.isdir(p)]:
                pbin = os.path.join(b, "pandoc")
                if os.path.exists(pbin):
                    os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                    try:
                        out = subprocess.check_output(["pandoc", "--version"], stderr=subprocess.STDOUT, text=True)
                        return out.splitlines()[0]
                    except Exception:
                        pass
            raise RuntimeError("Pandoc was downloaded but not detected in PATH.")
    except Exception as e:
        raise RuntimeError(
            "Pandoc chưa sẵn sàng. Thử tự động tải thất bại.\n"
            "Cách cài thủ công:\n"
            "- macOS: brew install pandoc\n"
            "- Ubuntu/Debian: sudo apt-get install -y pandoc\n"
            "- Windows: tải tại https://pandoc.org/installing.html\n"
            "- Streamlit Cloud: thêm file packages.txt, nội dung: pandoc\n"
            f"Chi tiết: {e}"
        )

# ---------- Utilities ----------
def normalize_quotes(s: str) -> str:
    return (s.replace('\xa0', ' ')
             .replace('–', '--')
             .replace('—', '---')
             .replace('“', '"').replace('”', '"')
             .replace("’", "'"))

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Read DOCX -> plain text (paragraph-joined) for math normalization."""
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
        try:
            os.remove(tmp_path)
        except Exception:
            pass

def to_markdown_with_math(src_text: str) -> str:
    """
    Normalize custom math markers into LaTeX math for Pandoc:
      - Block '([ ... ])'  --> $$ ... $$
      - Keep inline $...$ and display $$...$$ as-is.
    """
    s = src_text.replace("\r\n", "\n")
    pattern_block = re.compile(r"\(\[\s*(.*?)\s*\]\)", re.DOTALL)
    s = re.sub(pattern_block, lambda m: r"$$\n" + m.group(1).strip() + r"\n$$", s)
    # ensure spacing around display math for pandoc
    s = re.sub(r"\s*\$\$\s*\n", "\n\n$$\n", s)
    s = re.sub(r"\n\s*\$\$\s*", "\n$$\n\n", s)
    return s

def md_to_docx(md_text: str) -> bytes:
    """Markdown (with LaTeX math) -> DOCX (OMML equations) via Pandoc."""
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
    PDF -> DOCX (best-effort) via Pandoc.
    Native equation recovery is not guaranteed for arbitrary PDFs.
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
        except Exception: pass
        return data
    finally:
        try: os.remove(in_path)
        except Exception: pass

# ---------- UI blocks ----------
def page_header():
    st.markdown(f"## {APP_TITLE}")
    st.write("---")

def word_to_word_ui():
    st.subheader("DOCX (văn bản + mã công thức) → DOCX (phương trình Word/OMML)")
    st.write("Hỗ trợ marker công thức: `([ ... ])`, `$...$`, `$$...$$`.")
    up = st.file_uploader("Tải lên DOCX", type=["docx"], key="docx_up")
    c1, c2 = st.columns(2)
    with c1:
        title = st.text_input("Tiêu đề (tuỳ chọn)", "")
    with c2:
        author = st.text_input("Tác giả (tuỳ chọn)", "")

    if st.button("Convert Word → Word", type="primary"):
        if not up:
            st.warning("Hãy tải lên một file DOCX trước.")
            return
        try:
            ver = ensure_pandoc()
            st.info(f"Pandoc: {ver}")
            raw = up.read()
            text = extract_text_from_docx(raw)
            md = to_markdown_with_math(text)
            header = []
            if title:
                header.append(f"# {title}\n")
            if author:
                header.append(f"**{author}**\n")
            if header:
                md = "\n".join(header) + "\n" + md
            out_bytes = md_to_docx(md)
            st.success("Chuyển đổi thành công.")
            st.download_button(
                "Tải DOCX",
                data=out_bytes,
                file_name="converted_equations.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error(f"Lỗi: {e}")

def pdf_to_word_ui():
    st.subheader("PDF → DOCX (best-effort)")
    st.write("Dùng Pandoc để trích văn bản; việc khôi phục phương trình thành OMML **không đảm bảo** cho mọi PDF.")
    up = st.file_uploader("Tải lên PDF", type=["pdf"], key="pdf_up")
    if st.button("Convert PDF → Word"):
        if not up:
            st.warning("Hãy tải lên một file PDF trước.")
            return
        try:
            ver = ensure_pandoc()
            st.info(f"Pandoc: {ver}")
            pdf_bytes = up.read()
            out_bytes = pdf_to_docx(pdf_bytes)
            st.success("Chuyển đổi thành công.")
            st.download_button(
                "Tải DOCX",
                data=out_bytes,
                file_name="converted_from_pdf.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error(f"Lỗi: {e}")

def main_app():
    # Sidebar nav (left)
    st.sidebar.markdown(f"### {APP_TITLE}")
    st.sidebar.write("---")
    nav = st.sidebar.radio("Chức năng", ["Word → Word", "PDF → Word"], index=0)
    logout_button()  # logout button in sidebar

    # Right panel
    page_header()
    if nav == "Word → Word":
        word_to_word_ui()
    else:
        pdf_to_word_ui()

# ---------- Entry ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # Only show login (no sidebar/tabs)
    login_view()
else:
    main_app()
