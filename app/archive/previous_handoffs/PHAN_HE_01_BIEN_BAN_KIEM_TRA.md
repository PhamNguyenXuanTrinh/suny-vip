# SUNNY FLEX 3D — PHÂN HỆ 01

## Kết quả kiểm thử tại môi trường phát triển
- 129 cặp phương thức–đường dẫn API, 96 đường dẫn riêng biệt.
- 61/61 bài kiểm thử tự động đạt.
- Bổ sung API `/api/system/acceptance-matrix` để báo cáo các tiêu chí nghiệm thu và các điểm còn chặn.
- Giữ nguyên giao diện V86.

## CHƯA ĐẠT NGHIỆM THU
- Chưa đối chiếu và kiểm thử đầu cuối từng nút V86 với API và cơ sở dữ liệu.
- Chưa kiểm thử thiết bị Android, iPhone thật.
- Chưa nghiệm thu máy chủ HTTPS, sao lưu khôi phục khi có sự cố thật.
- Chưa kiểm thử thiết bị QR, cân, camera thật.

## Quy định
Không chuyển sang Phân hệ 02 cho đến khi tất cả tiêu chí bắt buộc có bằng chứng kiểm thử đạt.

## Chạy
`SUNNY_ADMIN_PASSWORD=<mat_khau_dai_an_toan> python -m pytest -q tests`
`SUNNY_ADMIN_PASSWORD=<mat_khau_dai_an_toan> python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765`

Lưu ý: Mật khẩu thử nghiệm trong một số bài kiểm thử không được dùng khi triển khai thực tế.
