# CONVERT FILE AND DATA (Streamlit App)

- **Login bằng mật khẩu** (env `APP_PASSWORD`), có Logout.
- Sidebar trái = menu; nội dung hiển thị bên phải.
- Footer giữa cuối trang: “bản quyền thuộc về TS DHN”.

## Chức năng
### 1) Word → Word
- **Giữ nguyên** các phương trình Word (OMML) sẵn có trong file.
- Tự động **chuyển** các *đoạn nguyên dòng* viết theo dạng `([ ... ])` thành **phương trình hiển thị** (DisplayMath).
- Không đụng phần chữ khác → không mất ký hiệu.
- Pipeline: **DOCX —(Lua filter)→ DOCX** (KHÔNG qua Markdown).

### 2) PDF → Word (best-effort)
- Dùng Pandoc để chuyển PDF sang DOCX. Khả năng phục hồi equation phụ thuộc file PDF nguồn.

## Chạy local
```bash
pip install -r requirements.txt
export APP_PASSWORD="your_password"      # macOS/Linux
# Windows PowerShell: $env:APP_PASSWORD="your_password"
streamlit run app.py
```

> Nếu máy không có Pandoc và pypandoc không tải được do chặn mạng, cài thủ công từ https://pandoc.org.
> Trên Streamlit Cloud: thêm file `packages.txt` với nội dung:
> ```
> pandoc
> ```

## Deploy Streamlit Cloud (qua GitHub)
- Repo cần có `app.py`, `requirements.txt`, (khuyến nghị) `packages.txt`.
- Trong Settings của app: đặt biến môi trường `APP_PASSWORD`.
- Deploy, login bằng mật khẩu, sử dụng các chức năng.

## Lưu ý soạn công thức
- Các khối `([ ... ])` nên chứa **LaTeX math đúng chuẩn** (ví dụ: `\rho`, `\nabla`, `\frac{...}{...}`).
- Các equation Word sẵn có trong file sẽ được **giữ nguyên**.
