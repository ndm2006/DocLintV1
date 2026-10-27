# Kiểm kê đề mục theo mẫu ĐATN 2019.1

Đã đối chiếu **51/51** tiêu đề/chú thích không rỗng của chính file mẫu; cả 51 có vai trò tự nhận và thông số phông, cỡ, đậm/nghiêng, căn lề, khoảng đoạn/giãn dòng khớp định dạng hiệu lực của nguồn. Đây là kiểm kê một mẫu, không phải precision/recall trên đồ án độc lập.

Nguồn: `Mẫu ĐATN_2019_version 1_1 (1).docx`. SHA-256: `5003fc2fab89b7fc1bead02e9d004607610cf8984e32230e12a0c903470917d5`. Không phân phối lại DOCX người dùng.

Mẫu có hai tiêu đề “DANH MỤC HÌNH VẼ”. Tiêu đề thứ hai đứng trước các mục Bảng nên được nhận là **danh mục bảng**, kèm cảnh báo `LIST_TITLE_MISMATCH`. Engine giữ chuỗi chữ; nếu cần sửa nhãn, người dùng sửa trực tiếp trong bản nguồn.

Heading4/Cap3 có định nghĩa trong mẫu nhưng không có đoạn không rỗng: TNR13 nghiêng, không đậm, trước 2 pt, căn đều. Kiểm chứng bằng fixture tổng hợp. Đề mục số bốn cấp nhập tay chưa đủ căn cứ vẫn được giữ.

ArnoPro là phông kế thừa của tiêu đề bìa trong mẫu. Hiển thị phụ thuộc phông hợp lệ được cài trên máy. Thông tin sinh viên, chữ ký, mã field/bộ nhớ đệm mục lục và nội dung tham khảo không bị viết lại. Các ngắt trang bổ sung là chính sách chuẩn hóa; bố cục trang và cập nhật field vẫn cần nghiệm thu Word.

Có thể chạy lại khi có nguyên bản mẫu:

```bat
python -m scripts.audit_template_headings "duong-dan-den-mau.docx" --output audit.json
```

[Dữ liệu kiểm kê đầy đủ](template_heading_audit.json). Các số dưới đây dùng twips cho khoảng đoạn/dòng; 20 twips = 1 pt.

| Khối | Nội dung nguồn | Vai trò | Phông / cỡ pt | Đậm / nghiêng | Căn | Trước / sau / dòng |
|---|---|---|---|---|---|---|
| b0 | TRƯỜNG ĐẠI HỌC BÁCH KHOA HÀ NỘI | cover_institution | ArnoPro / 15 | 1 / 0 | center | 60 / 0 / 264 |
| b7 | ĐỒ ÁN TỐT NGHIỆP | cover_title | ArnoPro / 25 | 1 / 0 | center | 60 / 0 / 264 |
| b8 | Thiết kế hệ thống tự động điều chỉnh | cover_subject | ArnoPro / 23 | 1 / 0 | center | 480 / 0 / 264 |
| b9 | nhiệt độ trong thiết bị sấy hoa quả | cover_subject_continuation | ArnoPro / 23 | 1 / 0 | center | 0 / 0 / 264 |
| b20 | ĐỀ TÀI TỐT NGHIỆP | assignment_title | Times New Roman / 13 | 1 / 0 | center | 480 / 0 / 264 |
| b26 | Lời cảm ơn | acknowledgement_title | Times New Roman / 13 | 1 / 0 | center | 480 / 0 / 264 |
| b31 | Tóm tắt nội dung đồ án | abstract_title | Times New Roman / 13 | 1 / 0 | center | 960 / 0 / 264 |
| b34 | MỤC LỤC | toc_title | Times New Roman / 13 | 1 / 0 | center | 60 / 0 / 264 |
| b36 | DANH MỤC HÌNH VẼ | list_figures_title | Times New Roman / 13 | 1 / 0 | center | 60 / 160 / 259 |
| b44 | DANH MỤC HÌNH VẼ | list_tables_title | Times New Roman / 13 | 1 / 0 | center | 60 / 160 / 259 |
| b50 | CÁC QUI ĐỊNH CHUNG | chapter | Times New Roman / 13 | 1 / 0 | center | 120 / 240 / 264 |
| b51 | Giới thiệu chung | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b64 | Sử dụng các định dạng văn bản theo qui định | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b65 | Qui định về căn lề văn bản | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b72 | Tạo lề cho văn bản in 2 mặt | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b78 | Tạo chương mới | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b83 | Tạo tiêu đề các cấp | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b87 | Định dạng phần nội dung các chương, mục | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b91 | Hình vẽ - Đồ thị | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b106 | Bảng biểu | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b116 | Bảng 1.1 Thống kê các thiết bị và giá thành | table_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b119 | Phương trình | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b132.tr0.tc2.p0 | PT 1.1 | equation_caption | Times New Roman / 12 | 0 / 1 | both | 60 / 200 / 240 |
| b148.tr0.tc2.p0 | PT 1.2 | equation_caption | Times New Roman / 12 | 0 / 1 | both | 60 / 200 / 240 |
| b150 | Tạo tham chiếu chéo giữa các đoạn văn bản | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b158 | Tạo danh mục tài liệu tham khảo | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b193 | Cập nhật lại các chú thích và tham chiếu | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b200 | Tạo danh mục hình vẽ | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b210 | Tạo danh mục bảng biểu | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b214 | Tạo trang mục lục | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b221 | Qui cách đóng quyển | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b235 | SỬ DỤNG CÁC BIỂU ĐỒ | chapter | Times New Roman / 13 | 1 / 0 | center | 120 / 240 / 264 |
| b236 | Giới thiệu về biểu diễn bằng đồ thị | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b245 | Đồ thị kiểu bánh | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b255 | Hình 2.1 Đồ thị kiểu bánh | figure_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b256 | Đồ thị kiểu thanh ngang | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b265 | Hình 2.2 Đồ thị kiểu thanh ngang | figure_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b266 | Đồ thị kiểu cột đứng | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b275 | Hình 2.3 Đồ thị kiểu cột đứng | figure_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b276 | Đồ thị kiểu đường | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b285 | Hình 2.4 Đồ thị kiểu đường | figure_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b286 | Đồ thị kiểu diện tích | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b295 | Hình 2.5 Đồ thị kiểu diện tích | figure_caption | Times New Roman / 12 | 0 / 1 | center | 60 / 200 / 240 |
| b298 | KẾT LUẬN | chapter | Times New Roman / 13 | 1 / 0 | center | 120 / 240 / 264 |
| b299 | Kết luận | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b302 | Hướng phát triển của đồ án trong tương lai | heading | Times New Roman / 13 | 1 / 0 | both | 120 / 0 / 264 |
| b306.sdtContent0.p0 | TÀI LIỆU THAM KHẢO | references_title | Times New Roman / 13 | 1 / 0 | center | 0 / 0 / 264 |
| b308 | PHỤ LỤC | appendix_title | Times New Roman / 13 | 1 / 0 | center | 120 / 240 / 264 |
| b309 | Chi tiết số liệu thí nghiệm | appendix_item_title | Times New Roman / 13 | 1 / 0 | both | 60 / 0 / 264 |
| b311 | Chi tiết các bước tính toán | appendix_item_title | Times New Roman / 13 | 1 / 0 | both | 60 / 0 / 264 |
| b313 | Chi tiết sơ đồ mô phỏng | appendix_item_title | Times New Roman / 13 | 1 / 0 | both | 60 / 0 / 264 |
