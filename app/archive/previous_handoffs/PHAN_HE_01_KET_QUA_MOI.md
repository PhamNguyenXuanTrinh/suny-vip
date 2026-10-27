# PHÂN HỆ 01 – BẢN CẬP NHẬT VÀ ĐIỀU KIỆN NGHIỆM THU

Ngày kiểm tra: 25/10/2026.

## Đã thực hiện
- Đồng bộ `public/index.html` với `public/v86.html` (giao diện V86 có Tổng kết ngày). Bản V86 gốc ban đầu vẫn lưu tại `archive/V86_GOC_BAT_BIEN.html`.
- Giữ các tuyến API nền tảng `/api/system/status`, `/api/system/roles`, `/api/system/api-catalog`.
- Thêm `scripts/backup_database.py` hỗ trợ backup SQLite bằng API sao lưu nhất quán, verify integrity_check và foreign_key_check, restore sang đường dẫn mới, không ghi đè tệp có sẵn.
- Thêm `tests/test_foundation_backup_phase01.py` kiểm thử sao lưu/khôi phục, ngăn ghi đè, từ chối dữ liệu hỏng.
- Chạy `SUNNY_ADMIN_PASSWORD=... python -m pytest tests -q`: **53 passed**.

## Chưa đủ điều kiện nghiệm thu triển khai
1. Chưa có kiểm thử tích hợp thực tế HTTPS/reverse proxy/Docker trên máy chủ đích.
2. Chưa có kiểm thử tải nhiều người dùng và khả năng khôi phục sau mất điện thật.
3. Chưa kiểm tra ma trận phân quyền mọi vai trò trên toàn bộ API; API catalog chỉ là danh sách tuyến, không chứng minh đủ nghiệp vụ.
4. Chưa có chính sách di trú schema có thể rollback, giám sát và cảnh báo production được nghiệm thu.
5. Chưa xác nhận tất cả nút giao diện V86 nối API thật; nhiều chức năng vẫn là mô phỏng.
6. Chưa kiểm tra vận hành AI Agent, cân, camera trên thiết bị thật.

**QUYẾT ĐỊNH: CHƯA ĐẠT NGHIỆM THU PHÂN HỆ 01; KHÔNG CHUYỂN PHÂN HỆ 02.**

## Lệnh kiểm tra
```
export SUNNY_ADMIN_PASSWORD='mat-khau-rieng-it-nhat-12-ky-tu'
python -m pytest tests -q
python scripts/backup_database.py backup --output /thu-muc-an-toan/backup.sqlite3
python scripts/backup_database.py verify --file /thu-muc-an-toan/backup.sqlite3
python scripts/backup_database.py restore --file /thu-muc-an-toan/backup.sqlite3 --output /thu-muc-moi/sunny.sqlite3
```
Không thực hiện khôi phục đè lên cơ sở dữ liệu đang hoạt động.
