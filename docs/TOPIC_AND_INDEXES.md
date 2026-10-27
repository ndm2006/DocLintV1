# Sửa tên đề tài và tạo các mục lục trên bản 0.1.3

Nhánh được tạo từ commit đã khôi phục `2f5b52ab5f670c4c97813cc8a9f637f41bf6c0af`. Phạm vi chỉ gồm cách viết tên đề tài và các mục lục/danh mục còn thiếu. Các thuộc tính bố trí bìa của bản 0.1.3 được kiểm tra giữ nguyên khi so với file `(6)`; không đưa lại các thay đổi khoảng đệm, header/footer hoặc cơ chế bố cục của các bản đã bỏ.

## Đối chiếu file người dùng gửi

- Gốc `01_do_an_tong_hop.docx`: SHA-256 `dbc063028679a4ee35eb830d0ce4df291750cfcffe009cef39f5263972563e99`.
- Kết quả `(6)`: SHA-256 `54ccf9a3a75bcc3f862e8e0ca7c37ead135e21cefe06db3a6c303cfe5dec5c6d`.
- Mẫu ĐATN 2019: SHA-256 `5003fc2fab89b7fc1bead02e9d004607610cf8984e32230e12a0c903470917d5`.

Trong file `(6)`, đề tài đã là ArnoPro 23 pt, đậm, căn giữa, nhưng nội dung `w:t` vẫn là `HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ`. Tắt thuộc tính caps không thể làm chữ nguồn đó tự thành chữ thường. Bản sửa xuất **Hệ thống quản lý mượn thiết bị**. Mẫu có tên đề tài kiểu câu ở hai đoạn: đoạn đầu viết hoa chữ đầu, đoạn tiếp bắt đầu bằng chữ thường. Giữ nguyên các run/ngắt dòng đã có, không viết lại từ ngữ hoặc đổi cách bố trí bìa.

Chỉ xử lý các đoạn nhận diện là đề tài bìa, không đổi tên trường, tên sinh viên hoặc Heading chương. Tên đề tài đã có chữ hoa/thường được giữ nguyên. Với nguồn toàn chữ hoa, hạ chữ thường cho các từ thông dụng nhận diện được; giữ các từ chưa đủ căn cứ đổi để tránh làm sai tên riêng/chữ viết tắt như API, HUST, và ghi cảnh báo trong báo cáo. Đây không phải bộ suy luận tên riêng tổng quát.

## Mục lục, danh mục

Thứ tự trong mẫu, cũng được ghi ở phần quy định: **MỤC LỤC → DANH MỤC HÌNH VẼ → DANH MỤC BẢNG → nội dung chương**.

- Tạo mục lục nếu chưa có; nếu chỉ có tiêu đề hoặc field rỗng `[chưa cập nhật trường]`, điền phần mục thay vì tạo thêm tiêu đề trùng.
- Có chú thích hình/bảng trong phần nội dung thì sinh danh mục tương ứng khi thiếu; không tạo danh mục rỗng khi chưa có mục phù hợp. Không lấy logo bìa hoặc công thức làm mục.
- Giữ các mục lục/danh mục của người dùng đã có nội dung. Danh mục nhập tay được giữ nguyên và có cảnh báo cần cập nhật thủ công.
- Các khối mới dùng TC/TOC/PAGEREF và bookmark riêng; số hiệu/tên mục lấy từ nguồn, không đặt tên thay người dùng. Các đề mục cần duyệt chưa được chấp thuận không được tự đưa vào.
- Mỗi tiêu đề danh mục mới bắt đầu trang riêng. Trên file thử hiện tại, bản dựng LibreOffice có mục lục ở trang 3, hình trang 4, bảng trang 5; không coi đây là nghiệm thu phân trang trên Microsoft Word.
- Xử lý lại file đã chuẩn hóa không tạo thêm khối hay mục trùng. Nội dung nguồn, ảnh, bảng, công thức, header/footer và các Style sẵn có được kiểm tra bảo toàn trong phạm vi của bản 0.1.3.

**Mở Word → Ctrl+A → F9 → cập nhật toàn bộ mục lục** để tính số trang. Dấu `?` là cache chưa được tính, không phải số trang chính xác. Trình xem DOCX trong trình duyệt không thay thế chế độ Print Layout của Word.

## Kiểm thử và file kết quả

Từ thư mục repository, dùng venv Python 3.12 đã cài requirements:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_topic_indexes.py
.venv/bin/python -m scripts.run_complex_tests
```

Kiểm thử trình duyệt, khi server một worker đang chạy và Chromium có sẵn:

```bash
CHROMIUM_PATH=/usr/bin/chromium npm run test:ui
```

Kết quả thực tế: **101 tests đạt**, kiểm thử Chromium đạt, hai ca tải lên → worker → tải DOCX thực qua HTTP và hai ca tải lại chính đầu ra đều đạt, các part Word không đổi sau lần hai, nhận diện/định dạng 51/51 tiêu đề/chú thích mẫu khớp như trước. Cả bốn DOCX tải xuống đã kiểm tra bằng **Microsoft Open XML SDK 3.3.0 / OpenXmlValidator, Office2013: 0 lỗi cấu trúc**. Kiểm tra này đã bắt được và giúp sửa thứ tự thuộc tính đoạn trong các field sinh mới; không thay thế việc mở/lưu file bằng Word.

Các ca mới gồm: file gốc và file `(6)`; kiểu câu và dòng đề tài tiếp nối; tên riêng/chữ viết tắt; thiếu hoàn toàn mục lục; tiêu đề danh mục rỗng; mục lục đã có; chỉ hình/chỉ bảng/cả hai/không có; không tạo trùng khi chạy lại; toàn vẹn chữ/ảnh/công thức và chặn sửa field ngoài kế hoạch. Các tests cũ được cập nhật cách tìm đoạn nguồn vì việc chèn danh mục làm thay đổi chỉ số vị trí; các kiểm tra bảo toàn vẫn được giữ.

- [Kết quả từ file gốc](examples/topic-indexes/01_from_original.docx).
- [Kết quả khi xử lý lại file (6)](examples/topic-indexes/02_from_previous_output.docx).
- [Bằng chứng kiểm tra](topic-indexes-validation.json).

Máy chủ thiếu ArnoPro; DOCX vẫn ghi đúng tên phông ArnoPro và cỡ 23 pt. Máy mở Word cần có phông hợp lệ. Chưa thực hiện mở/lưu/mở lại trên Microsoft Word, nên không tuyên bố toàn bộ bố cục đã nghiệm thu.
