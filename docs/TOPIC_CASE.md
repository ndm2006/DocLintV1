# Chỉ sửa kiểu chữ tên đề tài

Bản này dựa trực tiếp trên 2f5b52ab5f670c4c97813cc8a9f637f41bf6c0af, không chứa thay đổi sinh mục lục/danh mục của ab8149d.

Luồng xử lý chung đổi tên đề tài được nhận diện trên bìa từ chữ hoa toàn bộ sang kiểu câu, ví dụ `HỆ THỐNG QUẢN LÝ MƯỢN THIẾT BỊ` → `Hệ thống quản lý mượn thiết bị`. Đoạn tiếp nối tên đề tài không tự viết hoa chữ đầu. Giữ các run, ngắt dòng, định dạng và bố cục của bản nền. Không đổi hoa/thường thân bài, tên trường hoặc tên sinh viên. Lựa chọn giữ nguyên và vùng được bảo vệ vẫn được tôn trọng.

Để tránh làm sai tên riêng/chữ viết tắt, chỉ hạ chữ thường với các từ thông dụng nhận diện được; từ chưa rõ được giữ nguyên và cảnh báo. Không bảo đảm tự xác định mọi tên riêng trong đề tài tùy ý. Tên đề tài có kiểu hoa/thường sẵn được giữ nguyên.

Kiểm tra: `.venv/bin/python -m pytest -q` — 87 passed, 1 cảnh báo deprecation từ Starlette. Ca riêng: `tests/test_topic_case.py`. Đầu vào thật: `tests/fixtures/complex/01_do_an_tong_hop.docx`. File kết quả: `docs/examples/topic-case/01_do_an_tong_hop.docx`. Kiểm tra bảo toàn nội dung PASS; không mở trực tiếp trên Microsoft Word. Môi trường thiếu ArnoPro; file vẫn lưu phông theo bản nền, máy đọc cần cài phông để hiển thị đúng.
