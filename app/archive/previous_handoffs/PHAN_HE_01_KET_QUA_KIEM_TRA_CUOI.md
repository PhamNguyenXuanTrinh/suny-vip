# PHÂN HỆ 01 — KẾT QUẢ KIỂM TRA THỰC TẾ

Ngày: 25/10/2026

## Mã nguồn và API
- 128 cặp phương thức–đường dẫn API được đăng ký trong mã nguồn, 95 đường dẫn riêng biệt.
- Kiểm thử tự động: 60/60 đạt trong môi trường kiểm thử hiện tại.
- Đã bổ sung GET /api/system/readiness và GET /api/system/audit-summary.
- Giao diện V86 được giữ nguyên; có nút Tổng kết ngày theo bản đã chốt.
- Cơ sở dữ liệu SQLite có cấu trúc, API truy vấn, kiểm tra toàn vẹn và công cụ sao lưu/khôi phục.

## CHƯA ĐƯỢC NGHIỆM THU — KHÔNG ĐƯỢC CHUYỂN PHÂN HỆ 02
- V86 còn dùng localStorage: True. Chưa chứng minh 100% nút đã ghi/đọc dữ liệu qua API trung tâm.
- Chưa có biên bản kiểm thử trên điện thoại Android và iPhone thật.
- Chưa có bằng chứng kiểm thử cân, QR, camera thực tế.
- Chưa nghiệm thu HTTPS, Docker, máy chủ và kiểm thử tải ngoài môi trường thử nghiệm.
- 128 cặp API được đăng ký KHÔNG có nghĩa 128 API đã qua kiểm thử nghiệp vụ đầu cuối.
- AI Agent chưa được chứng minh tự động hoạt động theo nghiệp vụ thực.

## Quy tắc nghiệm thu
Chỉ đánh dấu ĐẠT sau khi có bảng từng nút V86 → phương thức và đường dẫn API → quyền → bảng dữ liệu → thao tác đọc/ghi → kịch bản và bằng chứng thử nghiệm; kiểm thử thiết bị thật và máy chủ; không có lỗi nghiêm trọng.

## Khởi chạy
pip install -r requirements.txt
SUNNY_ADMIN_PASSWORD='mat-khau-rieng-it-nhat-12-ky-tu' python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

Đăng nhập lấy Bearer token rồi truy cập GET /api/system/readiness, GET /api/system/api-catalog, GET /api/system/ui-contract, GET /api/system/audit-summary.
