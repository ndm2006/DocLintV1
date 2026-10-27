# DocLint · V0.1.2

Web chuẩn hóa DOCX tiếng Việt trong phạm vi V0.1, cập nhật nhận diện tự động và cấu hình **HUST20191_S11** từ file mẫu `Mẫu ĐATN_2019_version 1_1 (1).docx` người dùng cung cấp. Không phải bản nghiệm thu toàn bộ đặc tả V1.0.

## Chạy trên Windows

Cài **Python 3.12 64-bit**. Python 3.14 không tương thích với NumPy đang ghim. Tải repo mới, giải nén vào thư mục riêng, mở CMD tại thư mục đó:

```bat
py -3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install --upgrade pip
.venv312\Scripts\python.exe -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt
.venv312\Scripts\python.exe -m uvicorn doclint.app:app --port 8000 --workers 1 --no-access-log
```

Mở `http://localhost:8000`. Giữ CMD chạy; dùng cửa sổ CMD thứ hai cho lệnh kiểm thử. Dừng bằng Ctrl+C. Nếu đang dùng bản cũ, phải dừng server cũ và khởi động từ thư mục bản mới; tải lại trình duyệt để nhận JS mới. Không chép đè thư mục `.venv312` giữa hai bản repo.

Linux/macOS/cloud:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn doclint.app:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
```

Không cần API key, Node.js, cơ sở dữ liệu hay dịch vụ AI ngoài để chạy web. Node.js chỉ cần cho kiểm thử trình duyệt tùy chọn. Chỉ một worker server: phiên và hàng đợi lưu trong RAM; restart làm mất phiên. Trước khi mở Internet, cần HTTPS/reverse proxy có giới hạn upload và rate limiting; chưa phải triển khai công cộng đã được gia cố.

## Luồng mặc định và nhận diện

Tải DOCX → kiểm tra phù hợp với đồ án → phân tích → **tự chuẩn hóa các khối đủ căn cứ** → kiểm tra toàn vẹn → tải Word/báo cáo. Chỉ dừng ở màn hình xác nhận khi có trường hợp mơ hồ. Xóa phiên xóa cả lựa chọn tệp/tên/kết quả trên giao diện; phản hồi của phiên cũ không được cập nhật lên phiên mới.

Thuật toán trong `doclint/structure.py` kết hợp:

1. Style, basedOn/aliases, outline level, thuộc tính kế thừa và cấu hình numbering thật của Word. Heading có số tự động không bị nhầm thành danh sách.
2. Nhãn `CHƯƠNG n`, `CHƯƠNG I`, đề mục `n.m`/`n.m.k` và cây cha–con theo ngữ cảnh. Dòng `1 Tổng quan` cần có đề mục con tương ứng để coi là chương. Kiểm tra cha bị thiếu, số chương trùng/nhảy thứ tự, đề mục trùng hoặc mâu thuẫn Style.
3. ML Logistic Regression chạy cục bộ và bằng chứng bố cục để đề xuất vai trò cho tiêu đề ngắn không có nhãn rõ. Trường hợp này có thể cần xác nhận, mặc định giữ nguyên.

ML vẫn là baseline học từ ví dụ tổng hợp (`local-logreg-synthetic-0.1`); bộ giải cấu trúc revision `structure-context-0.3`. Không gọi LLM, không viết lại nội dung. Chưa có precision/recall trên tập đồ án thật độc lập; điểm quy tắc không phải xác suất chất lượng đã hiệu chỉnh. Không cam kết tự nhận đúng mọi đề mục không đánh số. Trước khi tạo phiên/worker, cổng kiểm tra trong `doclint/eligibility.py` kết hợp tiêu đề đồ án/loại văn bản và cấu trúc chương–đề mục. Tài liệu như báo cáo công việc/tiến độ hoặc thiếu cấu trúc phù hợp bị trả HTTP 422 `NOT_A_THESIS`/`THESIS_STRUCTURE_REQUIRED`, không tạo run, không xuất Word; giao diện yêu cầu chọn file khác. Từ “đồ án” hoặc tên file chứa từ đó không đủ để được nhận. Đây là kiểm tra dấu hiệu phù hợp, chưa phải bộ phân loại ngữ nghĩa tuyệt đối trên mọi tài liệu.

## Định dạng theo mẫu đã cung cấp

Profile và SHA-256 của nguồn nằm trong `doclint/template.py`; không phân phối lại nguyên bản mẫu người dùng.

- Thân bài: Times New Roman **13 pt**, căn đều, trước 3 pt, sau 0 pt; giãn dòng **1,1** (`w:line=264`, `lineRule=auto`), không dùng Exactly.
- Chương: 13 pt, đậm, căn giữa, chữ hoa bằng thuộc tính hiển thị để không thay chuỗi chữ, trước 6/sau 12 pt, ngắt trang, outline level 0.
- Đề mục đến `n.m.k`: 13 pt, đậm, không nghiêng, trước 6/sau 0 pt; căn đều theo kế thừa mẫu, outline level 1/2. Heading 4 có Style/outline rõ được định dạng theo mẫu: 13 pt, nghiêng, không đậm, trước 2 pt. Mức `n.m.k.l` chỉ nhập tay vẫn giữ nguyên khi thiếu căn cứ cấu trúc.
- Giữ numbering và Style hiện có của Heading đánh số tự động. Với đề mục đánh số nhập tay, thêm Style Heading riêng khi cần, không sửa Style dùng chung và không tạo thêm nhãn số. Các khai báo Style/relationship/content type mới được kiểm chứng bằng danh sách cho phép; Style cũ và defaults phải còn nguyên.
- Lời cảm ơn/tóm tắt: nhận diện riêng tiêu đề và các đoạn nội dung trước chương đầu, dừng tại mục lục/phần khác/chữ ký. TNR 13; tiêu đề đậm, căn giữa, trước **24 pt** (cảm ơn) / **48 pt** (tóm tắt) theo thuộc tính trực tiếp trong mẫu; nội dung căn đều, 1,1 dòng, trước 3 pt. Không gán thành Heading chương hoặc thêm numbering. Lời cảm ơn bắt đầu trang mới, tóm tắt theo sau cùng trang khi có thể; mục lục/danh mục bắt đầu trang mới mà không thay nội dung field; không tự giảm font/rút gọn để ép vừa trang. Báo số đơn vị theo khoảng trắng và cảnh báo 100–150/300; bố cục một trang vẫn chưa có validator trong ứng dụng.
- A4 và lề theo đúng twips trong mẫu: 11907 × 16840; trái 1985, phải 1418, trên/dưới 1134, gutter 0. Tương ứng A4 danh nghĩa, 3,5–2,5–2–2 cm với sai số quy đổi nhỏ. Áp dụng cho section có nội dung nhận diện được ở cả trang dọc và ngang; giữ hướng ngang, hoán đổi kích thước A4 đúng hướng. Có bảng gộp/lồng không còn là lý do bỏ qua lề. Section nhiều cột vẫn được giữ và báo lý do. Bảng inline có lưới hợp lệ bị vượt vùng chữ sẽ được thu chiều rộng bảng/cột/ô theo tỷ lệ, giữ text, số hàng/cột, ô gộp và XML bảng lồng. Không tự phóng bảng nhỏ hoặc thay vị trí bảng nổi; phần chưa hỗ trợ được cảnh báo.
- Nhận diện thêm tiêu đề trường/loại đồ án/tên đề tài trên bìa, đề tài tốt nghiệp, mục lục, danh mục hình/bảng, tài liệu tham khảo (kể cả trong content control), phụ lục/đề mục phụ lục và caption hình/bảng/phương trình (kể cả trong ô bảng). Tiêu đề bìa dùng **ArnoPro 15/25/23 pt** theo Subtitle của mẫu; cần phông hợp lệ trên máy mở Word. Caption dùng TNR12 nghiêng, dòng đơn; nhãn phương trình căn đều theo mẫu, caption hình/bảng căn giữa. Giữ numbering của phụ lục.
- Đã đối chiếu **51/51 tiêu đề/chú thích không rỗng trong chính file mẫu**, gồm định dạng hiệu lực; xem [bảng kiểm](docs/TEMPLATE_HEADINGS.md). Mẫu ghi nhầm danh mục bảng thành “DANH MỤC HÌNH VẼ”: hệ thống xác định vai trò danh mục bảng từ các mục Bảng theo sau và cảnh báo; giữ nguyên chữ nguồn.
- Chữ ký/thông tin cá nhân, phần đầu chưa nhận hỗ trợ, mục lục sinh tự động, danh sách thông thường, ảnh, OMML, mã field, hyperlink, bookmark thông thường, footnote/endnote, comment và track changes được giữ trong phạm vi bảo vệ. Bảng giữ nội dung/gộp ô, chỉ đổi kích thước theo kế hoạch khi quá rộng. Bookmark trên Heading không chặn định dạng Heading; ID và vị trí vẫn giữ.

Không sửa nội dung, khoảng trắng, số nhập tay, thứ tự khối hoặc dữ liệu học thuật. Chỉnh trực tiếp OOXML trên bản sao gốc; không dùng kết quả chuyển qua PDF/HTML để xuất lại DOCX.

## Cổng toàn vẹn và báo cáo

Trước công bố: xác nhận fingerprint/schema/quan hệ cha–con; gói ZIP/OOXML đọc lại được; đối chiếu cấu trúc XML theo khối, bảng/công thức/vùng khóa; so byte tài nguyên và các part không có thao tác được phép. Riêng Style/OPC chỉ cho thêm định nghĩa đã xác định trước, không sửa cấu trúc có sẵn. Bảng được phép đổi đúng thuộc tính chiều rộng bảng/lưới/ô trong kế hoạch; sửa chữ, merge hoặc bảng lồng vẫn làm cổng thất bại. Sai khác ngoài kế hoạch → FAILED, không cho tải candidate.

Báo cáo JSON có số chương/đề mục tự động, số khối cần duyệt, khối sửa, khối giữ và lý do, định dạng áp dụng, các section được sửa, version/hash và trạng thái kiểm tra. Kết quả vẫn **PARTIAL** vì chưa dựng và nghiệm thu bố cục/field Word. Đây không phải lỗi toàn vẹn và không có nghĩa toàn bộ mẫu đã đạt.

## Kiểm thử và tài liệu để đối chiếu

Windows:

```bat
.venv312\Scripts\python.exe -m pytest -q
.venv312\Scripts\python.exe -m scripts.make_demo
.venv312\Scripts\python.exe -m scripts.run_complex_tests
```

Demo đơn giản ở `.runtime\demo.docx`. Bộ mẫu phức tạp có sẵn trong [thư mục này](tests/fixtures/complex), gồm:

- [ZIP 6 DOCX gốc và hướng dẫn](tests/fixtures/complex/DocLint-bo-mau-phuc-tap.zip).
- [ZIP các cặp gốc/kết quả hiện tại để mở ngay](tests/fixtures/complex/DocLint-cap-goc-ket-qua.zip).
- [Hướng dẫn đối chiếu từng mẫu](tests/fixtures/complex/HUONG_DAN.md).

`run_complex_tests` không cần server và không chiếm cổng 8000; dùng API/worker riêng. Tạo thư mục mới trong `.runtime\complex-results`, có `01_GOC.docx`, `02_DA_XU_LY.docx`, báo cáo và lựa chọn duyệt; riêng mẫu 05 có `02_TU_CHOI.json` và **không có Word đầu ra**. Các lựa chọn theo nhãn do người viết mẫu đặt. Đầu ra này là kết quả chương trình, **không phải đáp án chuẩn độc lập**. Mở hai file cạnh nhau trên Word để kiểm tra.

Tất cả fixture là dữ liệu tổng hợp, không phải đồ án sinh viên thật và không phải tập nghiệm thu AI độc lập. Xem [đối chiếu V0.1 và bằng chứng](docs/V01_ACCEPTANCE.md). Để sinh lại input: `python -m scripts.make_complex_fixtures` bằng Python trong venv; không cần thêm thư viện.

Kiểm thử trình duyệt tùy chọn: server đang chạy, Node.js và Chromium có sẵn:

```bash
npm ci --cache /tmp/doclint-npm-cache
CHROMIUM_PATH=/usr/bin/chromium npm run test:ui
```

Bao gồm tự động hóa demo, chỉ duyệt ca mơ hồ, tải Word, reload/chạy lại/hủy, xóa/chọn tệp mới, phản hồi phiên cũ về chậm và mobile không tràn ngang, từ chối file không phải đồ án trước khi chạy, định dạng phần đầu và lề cả hai hướng trang. Ảnh kiểm tra nằm trong `.runtime`, không commit.

## Giới hạn còn lại

- Chưa có PDF/renderer trong ứng dụng, tự sửa tràn trang, tạo/cập nhật mục lục, số trang, bìa tự động hoặc chuẩn hóa mọi bảng/ảnh. Xem trước bố cục là tùy chọn ở V0.1; outline văn bản không phải PDF.
- Chưa mở/cập nhật/lưu/mở lại kết quả trên Microsoft Word trong cloud. Đọc/dựng thử bằng LibreOffice là kiểm tra tương thích bổ sung, không thay nghiệm thu Word hoặc chứng minh bố cục đạt chuẩn.
- Chưa có dữ liệu gán nhãn độc lập, đánh giá người dùng hay benchmark mục tiêu V1.0. Không tuyên bố tuân thủ 100% mọi quy định HUST.
- 20 MiB upload, 100 MiB giải nén, 10 MiB/XML, 2.000 mục ZIP, 200.000 nút XML tổng, độ sâu XML tối đa theo parser 256. Chặn DTD/entity, đường dẫn thoát/mục ZIP trùng, macro, chữ ký số và tài liệu bảo vệ; kiểm tra Content Types và quan hệ chính, không chỉ tin đuôi file.
- Tối đa 5 phiên, 1 worker tài liệu + 4 lượt chờ, 10 run/phiên; token bí mật riêng, TTL 30 phút từ tiếp nhận. Dọn RAM mỗi 10 giây; kiểm tra quyền/TTL và cổng công bố. Không gia hạn ngầm khi xem/chạy lại.
- Hủy/xóa thu hồi công bố ngay; worker có thể tiếp tục tính tới điểm kiểm soát rồi bỏ kết quả. Ngân sách 300 giây được kiểm tra tại các mốc, chưa có supervisor áp hard deadline. Không có cơ chế khôi phục phiên sau crash/restart hoặc cam kết xóa vật lý không thể phục hồi trên mọi hạ tầng.

Không đưa tài liệu người dùng, credential, `.venv*`, `.runtime` hoặc `node_modules` vào Git. API OpenAPI ở `/docs`. Mỗi cloud task đã được cách ly; dùng checkout hiện có, không cần tạo Git worktree.
