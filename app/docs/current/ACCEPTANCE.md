# Kiểm tra bản phát hành 2.2.0

Cập nhật ngày 26/10/2026 theo tài liệu SUNNY-ERP-AI-IMPLEMENTATION-001 v1.1. Kết quả dưới đây chạy trên dữ liệu QA riêng. Bộ cài khởi tạo doanh nghiệp trống và yêu cầu đặt tài khoản quản trị; không nạp các số liệu QA vào dữ liệu vận hành.

| Hạng mục | Kết quả và bằng chứng |
| --- | --- |
| Backend | 143/143 kiểm thử đạt, không lỗi hoặc bỏ qua, trên Python 3.13.16 Linux đi kèm bộ cài: 82 kiểm thử triển khai hiện tại và 61 kiểm thử hồi quy. Xem `backend_tests_bundled_linux.xml` và `backend_test_output_bundled_linux.txt`. |
| Hợp đồng yêu cầu | Đủ 102 method/path phân biệt trong mục 4.2 của tài liệu gốc; triển khai thực tế có 188 method/path. Xem `required_api_contract.json`, `api_inventory.json`, `openapi.json` và kiểm thử đối chiếu. |
| Cơ sở dữ liệu | 44 bảng baseline, 7 bảng hỗ trợ có mục đích, 7 migration. Toàn bộ 152 khóa ngoại vật lý khớp metadata, kiểm tra integrity/FK và so sánh Alembic không có sai lệch. Xem `schema_validation.json` và `schema.sql`. |
| Phân quyền | Kiểm thử tenant, chủ sở hữu CTV, cơ sở, phân công công nhân và vai trò kết hợp. Quyền của một vai trò toàn tổ chức không mở rộng vai trò cơ sở khác. Quản trị cơ sở không được quản lý tài khoản toàn tổ chức hay đọc tài liệu riêng của người khác. |
| Đồng thời | 8 tài khoản thực hiện 64 lần xuất kho, tồn từ 100 còn đúng 36. 8 yêu cầu gạch nợ đồng thời chỉ ghi được 6 khoản hợp lệ và từ chối 2 khoản vượt số dư. |
| Sản xuất nhiều công đoạn | Chuyển đúng lượng đạt giữa các công đoạn; phế phẩm cộng từ mọi công đoạn. Kiểm thử 10 đầu vào → 9 đạt/1 hỏng → 7 đạt/2 hỏng → nhập đúng 7, tổng phế phẩm 3. Có thử toàn bộ thành phế phẩm và đính chính làm mở lại công đoạn không còn đầu vào. Không tạo báo cáo hoặc tồn thành phẩm giả. |
| Tiền và công nợ | INTEGER VND, HALF_UP chính xác bằng phép toán số nguyên trong CHECK của dòng bán. Chặn hóa đơn vượt tổng số lượng đơn nguồn, sai đơn vị, phân bổ vượt số dư và sai đối tượng. Chi tiết chứng từ có số dư và lịch sử các lần phân bổ. |
| Nâng cấp có dữ liệu | Migration 0007 giữ ID dòng bán và liên kết hóa đơn đã tồn tại; tạo backup trước, rebuild trong transaction, kiểm tra FK trước commit. Rollback dữ liệu đã có yêu cầu phục hồi từ backup đã xác minh. Không sửa snapshot migration cũ. |
| Giao diện | TypeScript, ESLint và Vite build đạt. Có tìm kiếm, lọc, sắp xếp/phân trang ở máy chủ; giữ bộ lọc/trang trên URL khi quay lại. Lỗi hiển thị cạnh đúng trường. Sửa thông tin đầu chứng từ không thay ID dòng không đổi. |
| Trình duyệt | 54 kiểm tra: 15 cơ bản/phân quyền/điện thoại 390 px, 15 luồng mua → kho → công nhân sản xuất → giao → thanh toán, 11 thao tác bổ sung qua API/giao diện và 13 thiết lập/vận hành. Xem các tệp `browser_acceptance.json`, `full_workflow_acceptance.json`, `completeness_acceptance.json`, `desktop_acceptance_bundled_linux.json`. |
| Công việc và tài khoản | Đổi người nhận việc lưu lịch sử, thu hồi quyền từ phân công cũ và chống gửi lặp. Trang cá nhân có danh sách/thu hồi phiên; giới hạn mặc định 8 phiên đang hoạt động. Cây phòng ban dùng quan hệ và người quản lý đã lưu. |
| Báo cáo | AR/AP, tồn, sản xuất, dòng tiền và KPI dùng chứng từ thật. Báo cáo có hợp đồng phản hồi, phân trang, tổng số bản ghi và tổng số liệu của toàn bộ kỳ. Sản xuất có phút dừng máy. KPI sản lượng/phế phẩm theo m2 tại công đoạn cuối được ghi rõ, tách với tổng phế phẩm toàn lệnh. |
| Sao lưu/phục hồi | SQLite online backup cùng ảnh/PDF tham chiếu; hash, tài liệu và sổ nghiệp vụ được đối soát. Khôi phục sang profile mới, giữ dữ liệu cũ và thu hồi phiên. Cấu hình lỗi, ZIP sai/thiếu, ngưỡng không hợp lệ hoặc dữ liệu không khớp bị từ chối trước khi chuyển cấu hình. Giới hạn đồng nhất 4 GB sau giải nén và kiểm tra dung lượng trống. |
| Môi trường độc lập | Runtime Windows x86_64 và Linux x86_64 có trong bộ cài. Luồng mở mới, tạo quản trị, đổi mật khẩu, CRUD, upload/download, sao lưu/phục hồi và dừng/mở lại chạy bằng runtime Linux của gói. Xem `offline_bundle_check.json`. |
| Thành phần Windows | Python embedded 3.13.17 khớp SHA-256 chính thức; 31 thư viện runtime thỏa dependency Windows/Python 3.13; 50 EXE/DLL/PYD là PE x86_64. Đây là kiểm tra thành phần, chưa phải chạy trên Windows thật. |
| AI và múi giờ | Tool allowlist, quyền, lịch sử riêng, SSE, timeout được kiểm thử bằng provider QA. API key chưa cấu hình, không gọi OpenAI thật. Lưu UTC và chốt ngày theo Asia/Ho_Chi_Minh, có kiểm thử biên nửa đêm Việt Nam. |

Luồng trình duyệt mua đến thu tiền đối soát ra doanh thu trước VAT 135.000 VNĐ, phải thu/phải trả bằng 0 và tồn kho 186.664 VNĐ. Các giá trị được tính từ chứng từ đã thao tác qua giao diện, không gán số cho dashboard.

Hai cảnh báo thư viện được giữ trong log: alias AnyIO cũ của Starlette và chu trình quan hệ departments/employees khi sắp xếp metadata. Phép kiểm tra riêng toàn bộ 152 FK vẫn đạt. Hồ sơ kiểm thử 2.1 nằm tại `docs/history/2.1.0`; không dùng kết quả Python 3.12 của bản cũ để khẳng định đã thử bản 2.2 trên Python 3.12.

## Chưa nghiệm thu tại môi trường vận hành

- Windows thật, cài trên máy của Sunny, mạng Wi-Fi và Android/iPhone thật.
- Chuyển dữ liệu sản xuất cũ, vì chưa được cung cấp database thật.
- API key, hạn mức, chi phí và chất lượng phản hồi OpenAI của tài khoản Sunny.
- Vận hành dài hạn, Docker/HTTPS và thiết bị tại xưởng.
- Camera, cân, QR/OCR phần cứng, hóa đơn điện tử pháp lý, bảng lương và đa tiền tệ cần dự án tích hợp/nghiệm thu riêng theo phạm vi đã nêu trong tài liệu baseline.

Các kết quả QA xác nhận phần nghiệp vụ và bộ chạy đã kiểm tra; chưa phải chứng nhận nghiệm thu 100% môi trường sản xuất thực tế.
