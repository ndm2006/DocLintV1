# Đối chiếu phạm vi V0.1

Nguồn yêu cầu: phần V0.1 người dùng gửi trong hội thoại và đặc tả DocLint 1.1; nguồn định dạng bổ sung là file mẫu ĐATN 2019.1 người dùng vừa cung cấp. Tài liệu này mô tả phạm vi triển khai và bằng chứng kiểm tra, không thay biên bản nghiệm thu trên Microsoft Word.

| Yêu cầu V0.1 | Trước cập nhật | Hiện tại / giới hạn |
|---|---|---|
| P0: tải DOCX, xử lý thật, xuất DOCX dùng tiếp | Có luồng thật | Giữ luồng, bổ sung kiểm tra OPC và test API/trình duyệt; Word đích vẫn cần mở và kiểm tra thủ công |
| P0: giữ bản gốc; đọc đoạn/bảng/ảnh/Styles/section | Đã giữ; đọc Style/numbering chưa đủ | Giữ fingerprint và chạy từ gốc; giải basedOn/aliases/outline/defaults/numbering của Heading; giữ dữ liệu đối tượng |
| P0: một mẫu cố định | Thông số thân bài có; Heading/lề còn quá hạn chế | Profile trích từ mẫu có hash: TNR 13, line 264 auto, khoảng đoạn theo vai trò; Style Heading an toàn; lề theo từng section an toàn, không ép section đặc biệt |
| P0: AI phân loại chương/đề mục/thân bài/khối chưa rõ, kể cả chưa dùng Heading | ML tổng hợp, bắt duyệt mọi chương/đề mục | Kết hợp ngữ nghĩa Word, số/cây cha-con và ML cho ca mơ hồ. Tự nhận chương/đề mục có căn cứ; không coi mọi dòng in đậm là Heading. ML chưa được đánh giá trên đồ án thật độc lập |
| P0: kiểm tra kết quả nhận diện | Có kiểm tra cơ bản | Tái kiểm fingerprint/phân tích trước sửa; phát hiện cha thiếu, chương trùng/nhảy, đề mục trùng/mâu thuẫn Style; quyết định sai bị chặn |
| P0: chỉnh OOXML, không tái sinh nội dung | Chỉnh trực tiếp, chưa có Heading Style đầy đủ | Thêm Style nếu cần mà không đổi Style cũ/defaults; giữ numbering gốc, không nhân đôi nhãn nhập tay; font/spacing/paragraph/page theo kế hoạch |
| P0: bảo toàn theo vị trí, bảng, ảnh, công thức | Có cổng bảo toàn | Giữ cổng, mở rộng kiểm chứng Style/OPC theo phép thêm có giới hạn; test cố ý làm hỏng đối tượng phải bị chặn |
| P0: báo đã sửa/giữ/chưa hỗ trợ | Có báo cáo cơ bản | Thêm nhận diện tự động/cần duyệt, định dạng sau sửa, lý do giữ và section đã sửa; vẫn PARTIAL vì layout/field chưa kiểm tra |
| P1: duyệt ngoại lệ, cho giữ nguyên | Có nhưng xuất hiện quá nhiều | Chỉ hỏi khối mơ hồ. Mẫu 01 và 06 không hỏi; mẫu 02 hỏi 2 khối (tiêu đề không số và thiếu cấp cha) |
| Lỗi người dùng phản ánh: xóa/chọn DOCX mới | Không reset toàn bộ file/input | Reset tên, file object, input value, kết quả; khóa nút tới khi chọn file mới; phản hồi cũ không được làm sống lại phiên |

## Bổ sung V0.1.2 theo phản hồi kiểm thử

- Chuẩn hóa lề cả hai hướng trang dù section chứa bảng gộp/lồng; không đổi hướng ngang. Chỉ thu bảng inline vượt vùng chữ bằng các thuộc tính chiều rộng được phép, giữ ô gộp và dữ liệu.
- Nhận diện và định dạng riêng lời cảm ơn/tóm tắt theo mẫu (TNR13, tiêu đề đậm/căn giữa trước 24/48 pt, nội dung 1,1/căn đều). Đếm theo khoảng trắng và cảnh báo độ dài; không tuyên bố bố cục mọi tài liệu đều nằm một trang.
- Từ chối tài liệu không phù hợp trước tạo phiên/run; không còn trả PARTIAL với 0 khối sửa cho mẫu 05. Kiểm tra kết hợp dấu hiệu tiêu đề và cấu trúc, không chỉ tên file/từ khóa.
- Kiểm kê đủ 51 tiêu đề/chú thích không rỗng của mẫu: bìa, đề tài, chương/đề mục, lời cảm ơn/tóm tắt, mục lục/danh mục, tham khảo/phụ lục và caption; định dạng hiệu lực được đối chiếu từng khối. Heading4 được định nghĩa nhưng không có đoạn không rỗng trong mẫu, kiểm bằng fixture tổng hợp. Xem [bảng kiểm](TEMPLATE_HEADINGS.md). Nhận biết danh mục bảng ghi nhầm nhãn từ nội dung Bảng theo sau; cảnh báo và giữ chuỗi chữ.
- Hồ sơ hiện tại: `docs/validation-v0.1.2.json`. Hồ sơ 0.1.1 giữ làm mốc lịch sử; các thống kê trước đó không tự đại diện bản mới.

## Bổ sung V0.1.3: bìa mẫu tổng hợp

Tên đề tài không còn cần Style Subtitle; sinh viên và các trường có nhãn được nhận diện trong nhóm bìa. Áp phông/cỡ theo vai trò, căn giữa, chuẩn hóa khoảng trường–tiêu đề cho bìa ngắn; bìa sẵn đoạn đệm không nhận thêm khoảng đó. Giữ chữ, mã, đối tượng và cấu trúc gốc. Có hồi quy nhận diện, font/cỡ, ranh giới phần đầu, khoảng đệm, thuộc tính chữ xung đột và chạy hai lần; có dựng thử bổ sung ngoài ứng dụng. [Chi tiết](COVER_V013.md), [hồ sơ hiện tại](validation-v0.1.3.json). Hồ sơ 0.1.2 và báo cáo quá trình 0.1.2 giữ nguyên như mốc lịch sử.

## Điều gì không thuộc P0 của V0.1?

Tài liệu phạm vi ban đầu cho phép hoãn PDF xem trước, tự tạo bìa/mục lục, bố cục bảng/ảnh phức tạp, đo precision 98%, mục tiêu p95 và vòng đời hoàn chỉnh V1.0. Quyền truy cập tệp và giới hạn upload phải có nếu đưa lên mạng; ứng dụng đã có quyền phiên/TTL/giới hạn nhưng chưa phải cấu hình Internet production đã nghiệm thu.

## Căn cứ thuật toán và tiêu chuẩn

- `doclint/template.py`: thông số trích từ docDefaults và kế thừa Heading1–4/section trong nguồn. SHA-256: `5003fc2fab89b7fc1bead02e9d004607610cf8984e32230e12a0c903470917d5`.
- Heading1 có alias CHUONG, Heading2/3 có Cap 1/Cap 2; các Style đó có thể đánh số theo numbering chứ không có chữ “CHƯƠNG” trong `w:t`. Bộ giải mới xử lý trường hợp này.
- Thân bài line=264 auto, trước 60 twips. Chương trước 120/sau 240 twips; đề mục trước 120/sau 0 theo kế thừa. Heading 2/3 kế thừa căn đều; đoạn cuối dòng ngắn thường nhìn như căn trái.
- Số nhập tay không bị viết lại/chuyển tự động. Heading đã đánh số bằng Word giữ Style/numbering gốc; Style thêm không chứa numbering để tránh nhân đôi.
- Không tự thay mọi bảng/ảnh/phần đầu về định dạng thân bài. Mức n.m.k.l chỉ nhập tay, nội dung/gộp ô của bảng, ảnh nổi và khung được bảo vệ; V0.1.2 cho phép đổi lề section ngang và chiều rộng bảng inline theo kế hoạch.

## Bằng chứng và cách kiểm tra

- `python -m pytest -q`: hồi quy API/OOXML, nhãn thủ công trên fixture, ca cấu trúc không dùng Heading, Heading có số theo Style/numbering, quan hệ/cha thiếu/trùng, tính lặp lại, cổng chặn thay đổi Style/OPC ngoài phép, vòng đời/quyền phiên.
- `npm run test:ui`: demo tự động hoàn tất không có REVIEW_WAIT; mẫu mơ hồ chỉ có 2 lựa chọn; xóa phiên rồi chọn tên khác; cố tình giữ phản hồi phiên cũ tới sau lúc xóa; tải/reload/chạy lại/hủy/mobile.
- `python -m scripts.run_complex_tests`: kiểm tra 6 fixture: 5 mẫu đi qua API/worker và 1 mẫu phải bị từ chối trước worker; lựa chọn ca cần duyệt dùng nhãn được viết cùng fixture, không lấy dự đoán làm đáp án.
- `docs/validation-v0.1.1.json`: số đo trên chính các mẫu được ghi rõ nguồn gốc; không phải ước lượng chất lượng trên tài liệu ngoài tập này.

Nguồn DOCX HUST gốc và kết quả xử lý tại cloud không được commit vì là tệp người dùng. Chỉ lưu hash/profile và thống kê kiểm tra. Nguyên bản và đầu ra của các fixture tổng hợp được đọc/dựng thử qua LibreOffice; không dùng bản DOCX được LibreOffice lưu lại làm đầu ra engine. Microsoft Word là bước kiểm tra thủ công còn lại.

## Các tiêu chí chưa được chứng minh

Chưa có đồ án thật được gán nhãn độc lập để chứng minh độ chính xác hoặc ưu thế của ML so với chỉ dùng quy tắc; chưa có nghiệm thu Word không Repair/cập nhật field/lưu/mở lại; chưa có kiểm tra bố cục trang thật trong ứng dụng. Do đó không tuyên bố “tự nhận đúng mọi tài liệu”, “đạt 100% chuẩn HUST” hoặc “đã nghiệm thu mọi yêu cầu V1.0”.
