# Bộ DOCX kiểm thử phức tạp — DocLint

Đây là **dữ liệu tổng hợp do dự án tự tạo**, không phải đồ án sinh viên thật, mẫu HUST gốc hoặc tập nghiệm thu AI độc lập. Không có thông tin cá nhân. Các số liệu minh họa không phải kết quả nghiên cứu. Số trang phụ thuộc Word và phông cài trên máy; không cam kết sẵn số trang.

## Cách lấy và mở mẫu

- Giải nén `DocLint-bo-mau-phuc-tap.zip`: có 6 DOCX gốc, hướng dẫn này và `manifest.json`.
- Nếu muốn đối chiếu ngay, tải `DocLint-cap-goc-ket-qua.zip`: mỗi thư mục có sẵn `01_GOC.docx` và `02_DA_XU_LY.docx`. Đây là ảnh chụp kết quả của engine lúc tạo gói, KHÔNG phải đáp án chuẩn độc lập; đọc báo cáo JSON và tiêu chí bên dưới. Gói này không thay cho việc chạy lại trên mã mới.
- Có thể mở ngay DOCX trong Word rồi tải lên web. DOCX không chứa macro.
- Nếu đang dùng bản mã nguồn tải trước lần cập nhật này, hãy tải bản ZIP repo mới từ GitHub → Code → Download ZIP, giải nén vào **thư mục mới**, rồi cài môi trường Python 3.12 theo README. Bộ mẫu đã phát hiện hai lỗi bảo vệ công thức/đề mục sâu; bản cập nhật sửa các lỗi đó, không chỉ thêm tài liệu.
- Không lưu đè file gốc khi mở Word. Word có thể cập nhật field hoặc chuyển đổi nội bộ khi lưu; hãy so sánh hai bản trước khi tự lưu lại.

## Tạo sẵn cặp gốc / kết quả — Windows

Mở CMD mới, không cần dừng server đang chạy. Từ thư mục **repo đã cập nhật**, với Python 3.12 và thư viện đã cài:

```bat
.venv312\Scripts\python.exe -m scripts.run_complex_tests
```

Nếu môi trường của bạn có tên `.venv`, thay `.venv312` bằng `.venv`.

Lệnh chạy API/worker trong một tiến trình kiểm thử riêng, không chiếm cổng 8000 và không đụng các phiên trên web. Tạo thư mục mới trong `.runtime\complex-results\...`, in đường dẫn ở cuối. Mỗi mẫu có:

| Tệp | Ý nghĩa |
|---|---|
| `01_GOC.docx` | Bản đầu vào, chưa sửa |
| `02_DA_XU_LY.docx` | Kết quả của chương trình hiện tại |
| `03_LUA_CHON_XAC_NHAN.json` | Các vai trò đã xác nhận theo nhãn được viết cùng mẫu, nếu có màn hình duyệt |
| `04_BAO_CAO.json` | Thao tác thực tế, toàn vẹn và phần chưa kiểm tra |
| `05_KY_VONG_THU_CONG.json` | Nhãn/vùng giữ nguyên do người tạo mẫu xác định |

**File xuất không phải đáp án chuẩn độc lập.** Hãy đối chiếu với tiêu chí bên dưới. Chạy thêm `python -m pytest -q` bằng Python trong môi trường dự án để kiểm tra bất biến độc lập. PASS của script chỉ chứng minh API hoàn tất và cổng toàn vẹn báo đạt; chưa chứng minh Word mở không Repair hay bố cục đạt.

## Đối chiếu từng mẫu

### 01 — Đồ án tổng hợp

- Bìa giả, lời cảm ơn, tóm tắt, mục lục dạng field, 3 chương, 9 đề mục, 54 đoạn thân bài; phông/cỡ chữ cố ý lộn xộn, một bảng dữ liệu, ảnh sơ đồ, công thức phân số OMML, header/footer.
- Duyệt: chọn Chương cho dòng `CHƯƠNG n...`, Đề mục cho `n.m ...`; phần chưa chắc giữ nguyên. Xem toàn bộ nhãn trong manifest.
- Thân bài được sửa: TNR 13 pt, căn đều, Multiple 1.1, trước 3 pt. Chương đậm/căn giữa/ngắt trang; các số nhập tay không được nhân đôi.
- Bìa phải giữ cỡ lớn; mục lục/field, ảnh, công thức, bảng, header/footer và dữ liệu trong chúng giữ nguyên.
- **Lề chưa được sửa trong mẫu này** do có vùng bảo vệ; báo cáo phải nói rõ. Không được báo bố cục hoặc mục lục đã được xác minh.

### 02 — Đề mục mơ hồ

- Có chương 1/2, đề mục `1.1`, `1.1.1`, mức sâu `1.1.1.1`, dòng in đậm `Lưu ý quan trọng`, danh sách nhập tay và danh sách đánh số tự động.
- Chọn **Giữ nguyên** cho `Lưu ý quan trọng`, `1. Sao lưu...` và `2.3.1 Mục chưa có cha 2.3` nếu xuất hiện trong màn hình duyệt. Không để máy tự thêm cha hoặc biến mọi dòng in đậm thành heading.
- Mức sâu `1.1.1.1` và danh sách tự động phải được bảo vệ. Cấp được xác nhận có thể sửa, nhưng không đổi chuỗi chữ hoặc nhân đôi số.
- Ca cố ý thiếu cha phục vụ quan sát giới hạn kiểm tra cây hiện tại; chưa coi việc mô hình nhận ra lỗi đó là năng lực đã nghiệm thu.

### 03 — Bảng phức tạp và trang ngang

- Bảng có gộp ngang, gộp dọc và bảng lồng; ảnh trộn chữ; section dọc → ngang; bảng dài **46 hàng**, hàng đầu được đánh dấu lặp tiêu đề; header/footer có field số trang.
- Số hàng/cột, nội dung các ô, ô gộp, bảng lồng và ảnh phải giữ nguyên. Không được ép bảng trọn một trang hoặc tự giảm chữ để vừa.
- Giữ ngắt section, hướng ngang và hình học trang. Phân trang, ngắt hàng và hiển thị header/footer cần kiểm tra trong Word; chưa có kiểm chứng renderer tự động.

### 04 — Đối tượng học thuật

- Công thức OMML dạng phân số nằm cùng chữ, ảnh, bookmark, REF field, hyperlink đến example.org, footnote, endnote, comment và lịch sử thêm/xóa chưa chấp nhận.
- Các đoạn chứa đối tượng phải giữ nguyên; các part phụ phải giữ byte chính xác. Không biến công thức thành ảnh/chữ thường; không tự chấp nhận/reject track changes.
- Trong Word kiểm tra có thể bấm vào công thức để sửa; chú thích/bình luận vẫn còn. Bật Review → All Markup để xem thay đổi theo dõi.
- Không cần mở liên kết mạng. Không coi field giữ nguyên là field đã được cập nhật đúng.

### 05 — Không phải đồ án

- Báo cáo công việc có danh sách, bảng và ảnh, **không có chương**.
- Hành vi V0.1: tiếp nhận DOCX và trả PARTIAL với **0 khối sửa**, không tự từ chối theo loại tài liệu. Đây là giới hạn được ghi nhận, không phải một ca đạt nhận diện “không phải đồ án”.
- Tất cả nội dung/định dạng trong document.xml phải giữ nguyên về cấu trúc XML; không yêu cầu toàn bộ file ZIP có cùng hash vì engine đóng gói lại.

### 06 — Ca dương kiểm tra thân bài và lề

- 2 chương, 4 đề mục và **60 đoạn thân bài**; chỉ văn bản, không có bìa/bảng/ảnh/vùng khóa. Phông Arial/Calibri/Courier New, cỡ 10/11/14/15 pt; giãn dòng 1.5, lề cố ý sai.
- Xác nhận cả 2 chương và 4 đề mục. Kỳ vọng 66 khối được áp dụng định dạng.
- Thân bài TNR 13 pt, giãn dòng Multiple 1.1, căn đều; lề trái 3.5 cm, phải 2.5 cm, trên/dưới 2 cm; A4 dọc. Word có thể hiển thị lệch 0.01 cm do quy đổi twips.
- Không mất dấu tiếng Việt, số thập phân, ký hiệu ±, khoảng trắng hoặc thứ tự đoạn.

## Kiểm tra bằng Word

1. Mở `01_GOC.docx` và `02_DA_XU_LY.docx`; View → View Side by Side.
2. Chọn cùng một đoạn thân bài, kiểm tra font/cỡ chữ và Paragraph → Line spacing → Multiple 1.1.
3. Kiểm tra Layout → Margins chỉ với mẫu 06; đối chiếu hướng trang/section ở mẫu 03.
4. Kiểm tra bảng gộp, ảnh, công thức và ghi chú ở mẫu 03/04.
5. Có thể dùng Review → Compare để thấy khác biệt định dạng. Đây là hỗ trợ quan sát, không thay thế đối chiếu nội dung/đối tượng.
6. Nếu Word báo Repair hoặc thiếu đối tượng, ghi mẫu và bước tái hiện. **Các mẫu được kiểm tra gói OOXML và đọc thử bằng LibreOffice khi khả dụng; chưa nghiệm thu trực tiếp trên Microsoft Word.**

## Tái tạo và bảo trì

```bat
.venv312\Scripts\python.exe -m scripts.make_complex_fixtures
.venv312\Scripts\python.exe -m pytest -q
```

Generator và manifest xác định vai trò thủ công, không lấy nhãn từ model. Bộ hồi quy kiểm tra reproducibility, văn bản theo thứ tự, XML bảng/công thức, các part phụ và từng đoạn được ghi phải giữ. Không dùng các mẫu này vừa huấn luyện vừa báo cáo độ chính xác độc lập.
