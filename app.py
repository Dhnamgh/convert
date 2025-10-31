# app.py
import os
import re
import sys
import tempfile
import subprocess
import streamlit as st

APP_TITLE = "CONVERT FILE AND DATA"
PASSWORD_ENV = "APP_PASSWORD"  # set this env var to enable login

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

# ---------------- AUTH ----------------
def login_view():
    st.markdown(f"## {APP_TITLE}")
    st.write("---")
    st.title("🔐 Login")
    st.write("Nhập mật khẩu để truy cập ứng dụng.")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        real = os.environ.get(PASSWORD_ENV, "").strip()
        if not real:
            st.error("Server chưa cấu hình `APP_PASSWORD`. Hãy đặt biến môi trường trước khi chạy.")
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

# ---------------- Pandoc helpers ----------------
def run_pandoc(pandoc_bin: str, args: list, input_bytes: bytes | None = None) -> tuple[int, str, str]:
    """Run pandoc (absolute path) and return (returncode, stdout, stderr)."""
    proc = subprocess.Popen(
        [pandoc_bin] + args,
        stdin=subprocess.PIPE if input_bytes is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(input_bytes.decode("utf-8") if input_bytes is not None else None)
    return proc.returncode, out, err

@st.cache_resource(show_spinner=False)
def ensure_pandoc_cached() -> tuple[str, str]:
    """
    Ensure pandoc is available. Return (pandoc_bin_abs_path, version_line).
    Strategy:
      1) Try 'pandoc' from PATH
      2) Else use pypandoc.download_pandoc() and pypandoc.get_pandoc_path()
    """
    # 1) Try existing in PATH
    try:
        out = subprocess.check_output(["pandoc", "--version"], stderr=subprocess.STDOUT, text=True)
        return ("pandoc", out.splitlines()[0])
    except Exception:
        pass

    # 2) Try pypandoc managed binary (absolute path)
    try:
        import pypandoc
        pypandoc.download_pandoc()
        pandoc_path = pypandoc.get_pandoc_path()
        out = subprocess.check_output([pandoc_path, "--version"], stderr=subprocess.STDOUT, text=True)
        return (pandoc_path, out.splitlines()[0])
    except Exception as e:
        raise RuntimeError(
            "Pandoc chưa sẵn sàng và không thể tải tự động (có thể do môi trường chặn mạng).\n"
            "Cách cài thủ công khi deploy Cloud: thêm file `packages.txt` với nội dung: `pandoc`.\n"
            "Local: cài pandoc theo hệ điều hành (brew/apt/installer).\n"
            f"Chi tiết: {e}"
        )

# ---------------- Math normalization ----------------
def normalize_docx_math_with_pandoc_to_md(pandoc_bin: str, docx_bytes: bytes) -> str:
    """
    DOCX (có equation OMML và/hoặc text LaTeX) -> Markdown với $...$/$$...$$ (giữ toán).
    Dùng pandoc docx->md để KHÔNG mất phương trình.
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(docx_bytes)
        tmp.flush()
        in_path = tmp.name
    try:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        rc, out_txt, err_txt = run_pandoc(pandoc_bin, [
            in_path,
            "-t", "markdown+tex_math_dollars",
            "-o", out_path
        ])
        if rc != 0:
            raise RuntimeError(f"Pandoc docx->md lỗi:\nSTDERR:\n{err_txt}\nSTDOUT:\n{out_txt}")
        md = open(out_path, "r", encoding="utf-8").read()
        return md
    finally:
        try: os.remove(in_path)
        except: pass
        try: os.remove(out_path)
        except: pass

def apply_custom_math_markers(md_text: str) -> str:
    """
    Chuyển các khối '([ ... ])' -> $$ ... $$ trong Markdown (sau khi đã docx->md).
    """
    s = md_text.replace("\r\n", "\n")
    pattern_block = re.compile(r"\(\[\s*(.*?)\s*\]\)", re.DOTALL)
    s = re.sub(pattern_block, lambda m: r"$$\n" + m.group(1).strip() + r"\n$$", s)
    # đảm bảo khoảng trống quanh display math
    s = re.sub(r"\s*\$\$\s*\n", "\n\n$$\n", s)
    s = re.sub(r"\n\s*\$\$\s*", "\n$$\n\n", s)
    return s

def markdown_to_docx_with_pandoc(pandoc_bin: str, md_text: str) -> bytes:
    """
    Markdown (chứa $...$ / $$...$$) -> DOCX (equation OMML) bằng Pandoc.
    """
    with tempfile.TemporaryDirectory() as td:
        md_path = os.path.join(td, "input.md")
        out_path = os.path.join(td, "output.docx")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        rc, out_txt, err_txt = run_pandoc(pandoc_bin, [
            md_path,
            "-f", "markdown+tex_math_dollars",
            "-t", "docx",
            "-o", out_path
        ])
        if rc != 0:
            raise RuntimeError(f"Pandoc md->docx lỗi:\nSTDERR:\n{err_txt}\nSTDOUT:\n{out_txt}")
        return open(out_path, "rb").read()

# ---------------- UI blocks ----------------
def page_header():
    st.markdown(f"## {APP_TITLE}")
    st.write("---")

def word_to_word_ui():
    st.subheader("DOCX (văn bản + mã công thức) → DOCX (phương trình Word/OMML)")
    st.write("Hỗ trợ: phương trình Word có sẵn **vẫn giữ nguyên**; mã công thức dạng `([ ... ])`, `$...$`, `$$...$$` sẽ được chuyển thành equation.")

    with st.form("form_docx", clear_on_submit=False):
        up = st.file_uploader("Tải lên DOCX", type=["docx"], key="docx_up")
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Tiêu đề (tuỳ chọn)", "")
        with c2:
            author = st.text_input("Tác giả (tuỳ chọn)", "")
        submitted = st.form_submit_button("Convert Word → Word")

    if submitted:
        if not up:
            st.warning("Hãy tải lên một file DOCX trước.")
            return
        try:
            with st.spinner("Đang chuyển đổi..."):
                pandoc_bin, ver = ensure_pandoc_cached()
                st.info(f"Pandoc: {ver} ({pandoc_bin})")

                # 1) DOCX -> Markdown (giữ equation thành $...$/$$...$$)
                md = normalize_docx_math_with_pandoc_to_md(pandoc_bin, up.getvalue())

                # 2) Áp dụng quy tắc đổi '([ ... ])' -> '$$...$$'
                md = apply_custom_math_markers(md)

                # 2.5) Thêm header nếu có
                header = []
                if title:
                    header.append(f"# {title}\n")
                if author:
                    header.append(f"**{author}**\n")
                if header:
                    md = "\n".join(header) + "\n" + md

                # 3) Markdown -> DOCX (equation OMML)
                out_bytes = markdown_to_docx_with_pandoc(pandoc_bin, md)

            st.success("Chuyển đổi thành công (giữ nguyên equation, chuyển mã công thức).")
            st.download_button(
                "Tải DOCX",
                data=out_bytes,
                file_name="converted_equations.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error("Lỗi trong quá trình chuyển đổi. Chi tiết bên dưới:")
            st.exception(e)

def pdf_to_word_ui():
    st.subheader("PDF → DOCX (best-effort)")
    st.write("Pandoc sẽ cố gắng trích text và công thức; kết quả phụ thuộc PDF nguồn (không đảm bảo 100% equation).")

    with st.form("form_pdf", clear_on_submit=False):
        up = st.file_uploader("Tải lên PDF", type=["pdf"], key="pdf_up")
        submitted = st.form_submit_button("Convert PDF → Word")

    if submitted:
        if not up:
            st.warning("Hãy tải lên một file PDF trước.")
            return
        try:
            with st.spinner("Đang chuyển đổi..."):
                pandoc_bin, ver = ensure_pandoc_cached()
                st.info(f"Pandoc: {ver} ({pandoc_bin})")

                # PDF -> DOCX trực tiếp qua pandoc
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmpin:
                    tmpin.write(up.getvalue())
                    tmpin.flush()
                    in_path = tmpin.name
                try:
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmpout:
                        out_path = tmpout.name
                    rc, out_txt, err_txt = run_pandoc(pandoc_bin, [in_path, "-o", out_path])
                    if rc != 0:
                        raise RuntimeError(f"Pandoc pdf->docx lỗi:\nSTDERR:\n{err_txt}\nSTDOUT:\n{out_txt}")
                    out_bytes = open(out_path, "rb").read()
                finally:
                    try: os.remove(in_path)
                    except: pass
                    try: os.remove(out_path)
                    except: pass

            st.success("Chuyển đổi thành công.")
            st.download_button(
                "Tải DOCX",
                data=out_bytes,
                file_name="converted_from_pdf.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error("Lỗi trong quá trình chuyển đổi. Chi tiết bên dưới:")
            st.exception(e)

def main_app():
    st.sidebar.markdown(f"### {APP_TITLE}")
    st.sidebar.write("---")
    nav = st.sidebar.radio("Chức năng", ["Word → Word", "PDF → Word"], index=0)
    logout_button()
    st.markdown(f"## {APP_TITLE}")
    st.write("---")

    if nav == "Word → Word":
        word_to_word_ui()
    else:
        pdf_to_word_ui()

# ---------------- ENTRY ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_view()
else:
    main_app()
