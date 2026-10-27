# Tổng kiểm tra và sửa thực tế — 2.2.0

Đối chiếu trực tiếp mã nguồn/bộ cài 2.1 với đặc tả, kiểm thử sai quyền và sai dữ liệu, sửa lỗi rồi chạy lại toàn bộ. Không thêm dung lượng đệm vào bộ cài.

| Phát hiện hoặc phần thiếu | Kết quả bản 2.2 | Bằng chứng chính |
| --- | --- | --- |
| Vai trò toàn tổ chức và vai trò tại một cơ sở có thể bị trộn phạm vi | Tính quyền theo từng cặp vai trò/cơ sở rồi hợp các phạm vi hợp lệ | `test_completeness_audit.py`, `test_production_yield.py` |
| Thiếu API và thao tác đổi người nhận việc | Có API transactional/idempotent, giao diện, lịch sử và thu hồi quyền phân công cũ | Kiểm thử backend và `completeness_acceptance.json` |
| Thiếu hai đường dẫn/phương thức đúng đặc tả cho tài liệu và đọc thông báo | Thêm alias và cùng áp dụng quyền/rate limit | Đối chiếu 102 method/path và kiểm thử rate limit alias |
| Công đoạn sau nhận lại toàn lượng phát hành dù công đoạn trước đã có phế phẩm | Chuyển lượng đạt, cộng phế phẩm đúng toàn lệnh, xử lý hết phế phẩm và đính chính | `test_production_yield.py` |
| Hóa đơn liên kết có thể vượt tổng lượng đơn bán hoặc đổi đơn vị | Cộng lượng đã phát hành trước khi ghi sổ, khóa ghi tránh đua và chặn sai đơn vị | `test_completeness_audit.py` |
| CHECK chiết khấu dùng phép chia REAL, có thể từ chối chiết khấu hợp lệ sau làm tròn | Migration 0007 thay bằng phép toán INTEGER chính xác, giữ ID/FK và backup | `test_exact_discount_migration.py` |
| Sửa liên hệ chính chưa tự bỏ liên hệ chính cũ | Đổi liên hệ chính trong một transaction | `test_completeness_audit.py` |
| Lý do xuất kho thủ công chưa đi vào audit | Lưu lý do gắn đúng bút toán | `test_completeness_audit.py` |
| Biểu mẫu gửi lại toàn bộ dòng khi chỉ sửa đầu chứng từ và không xóa được giá trị tùy chọn | PATCH phần thay đổi, gửi NULL khi xóa ô tùy chọn, giữ dòng không đổi | Kiểm tra giao diện thực và API trong `completeness_acceptance.json` |
| Bộ lọc/sắp xếp, lỗi cạnh trường, cây phòng ban, lịch sử phân bổ và quản lý phiên còn thiếu giao diện | Hoàn thiện thao tác thực, dữ liệu lấy từ server, có kiểm thử qua trình duyệt | `completeness_acceptance.json`, `browser_acceptance.json` |
| Báo cáo sản xuất thiếu tổng dừng máy; danh sách báo cáo bị cắt ở 100 dòng | Có phút dừng, phân trang, tổng toàn kỳ và response schema | Kiểm thử báo cáo/phân trang và OpenAPI |
| Có thể tạo backup lớn hơn mức công cụ phục hồi chấp nhận; cấu hình phục hồi chưa kiểm tra đủ | Chặn tạo vượt 4 GB, kiểm tra dung lượng trống, cấu hình và đối soát nghiệp vụ trước khi đổi profile | `test_desktop_operations.py` |

Các kiểm tra mới về số tiền/sản lượng bằng 0 cải thiện lỗi trả về 422 và gắn đúng trường; cơ sở dữ liệu cũ vốn đã có một số CHECK chặn số 0, nên không quy tất cả các trường hợp này thành lỗi ghi sổ của bản 2.1.

Kết quả và giới hạn nghiệm thu xem `ACCEPTANCE.md`. Không khẳng định các thiết bị hoặc OpenAI thật đã được nghiệm thu khi chưa có phép thử tương ứng.
