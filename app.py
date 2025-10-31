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
def run_pandoc_abs(pandoc_bin: str, args: list, input_text: str | None = None) -> tuple[int, str, str]:
    """Run pandoc with absolute path. Return (rc, stdout, stderr)."""
    proc = subprocess.Popen(
        [pandoc_bin] + args,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(input_text if input_text is not None else None)
    rc = proc.returncode
    return rc, out, err

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

# ---------------- Lua filter for markers ([ ... ]) ----------------
CONVERT_MARKERS_LUA = r'''
-- convert_markers.lua
-- Change lines of the form: ([ ... ])  -->  Display Math (OMML)
-- Keep existing Word equations (OMML) intact.

local utils = require('pandoc.utils')

function Para(el)
  local s = utils.stringify(el)
  local inner = s:match("^%(%[%s*(.-)%s*%]%)$")
  if inner then
    return pandoc.Para({ pandoc.Math('DisplayMath', inner) })
  end
  return nil
end
'''

def convert_docx_docx_with_lua(pandoc_bin: str, docx_bytes: bytes, title: str = "", author: str = "") -> bytes:
    """
    DOCX → DOCX, using Lua filter:
    - Preserve existing OMML equations,
    - Convert '([ ... ])' full-line blocks into DisplayMath,
    - Do not touch other text.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path  = os.path.join(td, "in.docx")
        out_path = os.path.join(td, "out.docx")
        lua_path = os.path.join(td, "convert_markers.lua")

        with open(in_path, "wb") as f:
            f.write(docx_bytes)
        with open(lua_path, "w", encoding="utf-8") as f:
            f.write(CONVERT_MARKERS_LUA)

        args = [in_path, "-o", out_path, "--lua-filter", lua_path]
        rc, out_txt, err_txt = run_pandoc_abs(pandoc_bin, args)
        if rc != 0:
            raise RuntimeError(
                "Pandoc error (DOCX→DOCX with Lua filter).\n"
                f"Command: {' '.join([pandoc_bin] + args)}\n"
                f"STDOUT:\n{out_txt}\n"
                f"STDERR:\n{err_txt}\n"
            )
        with open(out_path, "rb") as f:
            return f.read()

def pdf_to_docx(pandoc_bin: str, pdf_bytes: bytes) -> bytes:
    """PDF → DOCX (best-effort) via pandoc."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmpin:
        tmpin.write(pdf_bytes)
        tmpin.flush()
        in_path = tmpin.name
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmpout:
            out_path = tmpout.name
        rc, out_txt, err_txt = run_pandoc_abs(pandoc_bin, [in_path, "-o", out_path])
        if rc != 0:
            raise RuntimeError(
                "Pandoc error (PDF→DOCX).\n"
                f"Command: {' '.join([pandoc_bin, in_path, '-o', out_path])}\n"
                f"STDOUT:\n{out_txt}\n"
                f"STDERR:\n{err_txt}\n"
            )
        with open(out_path, "rb") as f:
            data = f.read()
        try: os.remove(out_path)
        except: pass
        return data
    finally:
        try: os.remove(in_path)
        except: pass

# ---------------- UI blocks ----------------
def page_header():
    st.markdown(f"## {APP_TITLE}")
    st.write("---")

def word_to_word_ui():
    st.subheader("DOCX (văn bản + mã công thức) → DOCX (phương trình Word/OMML)")
    st.write("Giữ nguyên equation Word có sẵn; chuyển các đoạn nguyên dòng dạng `([ ... ])` thành phương trình hiển thị.")
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
                raw_docx = up.getvalue()
                out_bytes = convert_docx_docx_with_lua(pandoc_bin, raw_docx, title, author)
            st.success("Chuyển đổi thành công.")
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
    st.write("Pandoc cố gắng trích text và công thức; kết quả phụ thuộc PDF nguồn (không đảm bảo 100%).")
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
                out_bytes = pdf_to_docx(pandoc_bin, up.getvalue())
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

    page_header()
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
