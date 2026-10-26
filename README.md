# DocLint · V0.1

Web thử nghiệm chuẩn hóa định dạng DOCX tiếng Việt theo cấu hình **HUST20191_S11**: Times New Roman 13 pt, căn đều, giãn dòng **1,1** (`w:line=264`, `auto`). Dựa trên đặc tả DocLint 1.1 và phạm vi V0.1 được cung cấp. Chưa phải bản nghiệm thu toàn bộ đặc tả.

## Chạy nhanh

Yêu cầu Python **3.12**, Linux/macOS/Windows. Không cần API key, Node.js, cơ sở dữ liệu hay dịch vụ AI ngoài.

```bash
python -m venv .venv
# Linux/macOS
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn doclint.app:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
# Windows: thay .venv/bin/python bằng .venv\Scripts\python.exe
```

Dùng cổng 8000 qua trình duyệt trong môi trường triển khai. API OpenAPI tại `/docs`. Chỉ chạy **một tiến trình**: phiên và hàng đợi lưu trong RAM, không dùng `--workers` lớn hơn 1. Khởi động lại dịch vụ làm mất phiên và tệp tạm. Trước khi mở Internet, đặt HTTPS/reverse proxy có giới hạn upload và rate limiting; chưa coi bản demo là triển khai công cộng đã được gia cố.

## Demo trong 5 phút

```bash
.venv/bin/python scripts/make_demo.py
```

1. Tải `.runtime/demo.docx` lên giao diện. Tệp được sinh bằng dữ liệu giả, có đoạn tiếng Việt, đề mục, bảng, ảnh và công thức OMML.
2. Chọn **Chuẩn hóa tài liệu**. AI nội bộ đề xuất vai trò; các chương/đề mục luôn phải xác nhận. Mặc định phần cần duyệt được **giữ nguyên**.
3. Xác nhận chương và đề mục hợp lý; tiếp tục chuẩn hóa.
4. Tải DOCX và báo cáo JSON. So sánh bằng Word: thân bài 13 pt, khoảng dòng 1,1; bảng, ảnh, công thức và chữ không đổi.
5. Thử chạy lại từ bản gốc, hủy và xóa phiên. Quyền phiên lưu trong `sessionStorage` của tab; tải lại trang trong cùng tab khôi phục được phiên còn hạn.

**Mở, cập nhật trường, lưu rồi mở lại trên Microsoft Word vẫn là bước nghiệm thu thủ công chưa thực hiện trong môi trường này.**

## Có gì trong bản đầu?

- Giao diện tiếng Việt, responsive; kéo thả DOCX, giai đoạn thực tế, màn hình duyệt theo khối với ngữ cảnh, kết quả, tải Word/báo cáo, chạy lại/hủy/xóa.
- FastAPI và một worker nội bộ; token bí mật ngẫu nhiên của phiên, chỉ lưu hash phía máy chủ. UUID không cấp quyền; API dữ liệu yêu cầu `Authorization: Bearer …`.
- Bộ phân loại Logistic Regression chạy cục bộ, ghim revision `local-logreg-synthetic-0.1`. Đầu vào gồm đặc trưng độ dài, số đề mục, chữ hoa, đậm và cỡ chữ; khởi tạo xác định từ các ví dụ tổng hợp có phiên bản. Không gọi LLM, không tự viết lại nội dung. **Chưa được đánh giá độc lập; điểm mô hình chưa phải xác suất chính xác đã hiệu chỉnh.** Đây là baseline ML có thể thay thế, chưa chứng minh tốt hơn bộ quy tắc hoặc đạt mục tiêu precision 98%.
- Inspector kiểm tra ZIP, XML, quan hệ nội bộ, mã khối/fingerprint; kiểm tra nhãn và cấp cha cơ bản trước khi sửa.
- Chỉnh trực tiếp thuộc tính OOXML của đoạn/chữ; không chuyển đổi DOCX qua HTML/PDF để xuất lại. Mỗi run lấy lại bản gốc. Không sửa Style dùng chung, numbering, dữ liệu hoặc nhãn đánh số nhập tay.
- Thân bài: TNR 13, căn đều, trước 3 pt, giãn dòng 1,1. Chương: đậm, chữ hoa bằng thuộc tính, căn giữa, ngắt trang, trước 6/sau 12 pt. Đề mục đến `n.m.k`: đậm, đặt outline level. **Chưa tạo bộ Heading Styles/aliases hoàn chỉnh theo mẫu**; chưa chuyển nhãn số tự động.
- Chỉ đổi trang A4/lề 3,5–2,5–2–2 cm trong tài liệu một section dọc, toàn bộ khối được phép sửa. Nếu có bìa/vùng bảo vệ/bảng/ảnh/công thức/section đặc biệt, giữ hình học trang để tránh làm đổi vùng bảo vệ; báo rõ trong JSON. Không tuyên bố lề đã sửa trong các tài liệu này.
- Kiểm chứng cấu trúc XML chính sau khi loại đúng vùng định dạng được phép; các part khác đối chiếu **byte chính xác**, bao gồm ảnh, bảng/phần nhúng, relationships, styles, comments, headers, footers. Đọc lại gói trước công bố. Sai khác ngoài phạm vi làm FAILED, không có đường tải candidate.
- Trả **PARTIAL** vì chưa dựng/kiểm tra bố cục, chưa xác minh trường Word. Hiển thị cấu trúc văn bản, không giả là PDF hay phân trang thật.

## Giới hạn chủ động

- Tài liệu tiếng Việt, một cột, khuyến nghị có nhãn `CHƯƠNG …`. Vùng trước chương đầu được giữ như phần đầu/bìa. Tài liệu không nhận ra chương có thể được giữ toàn bộ; báo cáo ghi số khối thực sự đã sửa.
- Giữ nguyên bảng, ảnh, OMML, field, hyperlink, bookmark, danh sách, lịch sử sửa, comment/footnote và vùng phức tạp. Không hứa bố cục không đổi do đoạn bên cạnh đã đổi định dạng. Mục lục, tham khảo, tóm tắt, phần đầu và mức sâu hơn `n.m.k` được bảo vệ.
- Chưa có PDF/renderer, kiểm tra tràn trang, tạo/cập nhật mục lục, số trang, bìa tự động, chuẩn hóa bảng/ảnh, mô hình ngôn ngữ pretrained hay bộ dữ liệu nghiệm thu độc lập. Không báo tuân thủ 100% mẫu.
- 20 MiB upload; 100 MiB giải nén; 10 MiB/một XML; 2.000 mục ZIP; 200.000 nút XML tổng; XML parser giới hạn độ sâu mặc định 256. Chặn mục trùng, đường dẫn thoát, DTD/entity, macro, chữ ký số và tài liệu có documentProtection.
- Tối đa 5 phiên, 1 worker + 4 lượt chờ, tối đa 10 run/phiên; TTL 30 phút tính từ tiếp nhận, không gia hạn khi xem/chạy lại. Dọn RAM định kỳ 10 giây, kiểm tra TTL mỗi truy cập và ngay trước công bố.
- Hủy/xóa thu hồi công bố ngay; worker đang tính có thể tiếp tục tới điểm kiểm soát rồi bỏ kết quả. Ngân sách 300 giây được kiểm tra tại các mốc; chưa có supervisor giết tiến trình theo hard deadline. Không có renderer hay truy cập mạng từ engine.
- Kho RAM không tồn tại qua restart, không có cơ chế phục hồi crash. Không tuyên bố xóa vật lý không thể khôi phục trên hạ tầng.

## Kiểm thử

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

Suite gồm luồng API thật với worker, chuẩn hóa thân bài/đề mục, bảo toàn text theo vị trí, bảng, ảnh và OMML; quyền phiên, TTL, hủy/xóa/chạy lại, quyết định sai, XML/ZIP bất thường, lề trong ca an toàn và giữ section ngang. Dữ liệu test là dữ liệu tổng hợp, không phải tập nghiệm thu AI.

Kiểm thử trình duyệt tùy chọn (Node.js và Chromium cài sẵn), chạy cùng server:

```bash
npm ci --cache /tmp/doclint-npm-cache
.venv/bin/python scripts/make_demo.py
CHROMIUM_PATH=/usr/bin/chromium npm run test:ui
```

Tải lên → xác nhận → tải Word → reload → chạy lại → hủy → xóa; kiểm tra mobile không tràn ngang. Ảnh kiểm tra và DOCX đầu ra nằm trong `.runtime/`, không commit.

## Cấu trúc

```text
doclint/engine.py       kiểm tra gói, phân tích, bảo vệ, sửa, cổng toàn vẹn
doclint/recognizer.py   baseline ML nội bộ có phiên bản
doclint/app.py          API, quyền phiên, TTL, hàng đợi và công bố
doclint/static/         giao diện HTML/CSS/JS không cần build
scripts/make_demo.py    DOCX thử tổng hợp, không có dữ liệu cá nhân
tests/                 hồi quy API/OOXML và smoke trình duyệt
```

Tài liệu người dùng tải lên, đặc tả đính kèm và credential không được đưa vào Git. Không có tài khoản người dùng hay analytics. Cấu hình mẫu nằm trong `engine.TEMPLATE`; thay đổi cần revision và kiểm thử. Bước tiếp theo: tập dữ liệu gán nhãn/tách biệt để đánh giá AI, mẫu DOCX gốc để hoàn thiện Styles, renderer cách ly và nghiệm thu trên Microsoft Word.
