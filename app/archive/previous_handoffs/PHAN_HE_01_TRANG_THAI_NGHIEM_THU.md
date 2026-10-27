# SUNNY FLEX 3D – PHÂN HỆ 01: KIỂM THỬ VÀ NGHIỆM THU

**Quyết định: CHƯA ĐẠT – KHÔNG CHUYỂN SANG PHÂN HỆ 02.**

## Đã thực hiện
- Giữ nguyên giao diện V86 và nút Tổng kết ngày hiện có.
- Bổ sung `POST /api/auth/logout` thu hồi token; kiểm thử đăng xuất thành công và token cũ không còn truy cập.
- Bổ sung `GET /api/system/ui-contract` (chỉ giám đốc) kiểm kê API và tình trạng kết nối giao diện. Không tuyên bố các nút đã liên thông khi chưa có chứng cứ.
- Kiểm thử mã nguồn: **55/55 đạt** (chạy bằng `SUNNY_ADMIN_PASSWORD='phase01-test-secret-long' python -m pytest -q tests`).

## Chưa đạt – yêu cầu bắt buộc
1. Giao diện V86 hiện lưu dữ liệu bằng localStorage và chưa kết nối đầy đủ API xác thực và Database trung tâm. Chưa có đối chiếu từng nút với API.
2. Chưa kiểm thử thực tế trên điện thoại Android, iPhone và các thiết bị máy tính mục tiêu.
3. Chưa nghiệm thu phân quyền tất cả vai trò/tất cả API; chưa thử tải đồng thời, mất mạng, khôi phục thảm họa và triển khai HTTPS máy chủ thật.
4. AI Agent và thiết bị cân/camera/QR chưa kiểm thử tích hợp thực tế.
5. Các nghiệp vụ ERP mở rộng có mã nguồn không được coi là hoàn thành trong phạm vi Phân hệ 01.

## Hướng dẫn kỹ thuật
- Tạo môi trường Python và cài `requirements.txt`.
- Đặt biến môi trường `SUNNY_ADMIN_PASSWORD` có độ dài tối thiểu 12 ký tự trước lần khởi động đầu tiên.
- Chạy `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765`.
- Đăng nhập `POST /api/auth/login`, dùng Bearer token để gọi `GET /api/system/api-catalog` và `GET /api/system/ui-contract`.
- Giao diện V86 là bản xem trước với dữ liệu mô phỏng, không được sử dụng làm dữ liệu kế toán/sản xuất thật.
- Chỉ chuyển phân hệ sau khi có bảng đối chiếu từng thao tác UI→API→DB và biên bản nghiệm thu trên thiết bị thật.
