# SUNNY AI FLEX 3D — PHÂN HỆ 01: NỀN TẢNG ERP

## Mục đích
Giữ nguyên giao diện V86 hiện có, tạo hợp đồng kỹ thuật thống nhất cho các phân hệ tiếp theo. Không đổi màu, menu, bố cục hay loại bỏ nút Tổng kết ngày.

## Đã bổ sung bằng mã nguồn
- `GET /api/system/status`: kiểm tra cơ sở dữ liệu sau xác thực.
- `GET /api/system/roles`: liệt kê vai trò và quyền; chỉ giám đốc được truy cập.
- `GET /api/system/api-catalog`: xuất danh mục phương thức/đường dẫn API hiện có; chỉ giám đốc được truy cập.
- `tests/test_foundation_phase01.py`: kiểm tra tuyến API, xác thực và tệp giao diện.
- Các tệp giao diện `public/index.html`, `public/v86.html`, `public/app.html` giữ nguyên từng byte so với nguồn.

## Các thành phần nền tảng kế thừa từ mã nguồn hiện có
- FastAPI, đăng nhập, token, phân quyền theo vai trò, SQLite, ghi nhật ký và API nghiệp vụ đã có.
- Tài liệu OpenAPI tự sinh: `/api/openapi.json`; trang thử API `/api/docs`.
- Không được xem số tuyến API là số nghiệp vụ đã hoàn thiện.

## Việc kỹ thuật phải xác minh trước nghiệm thu giai đoạn 01
1. Chốt cấu trúc dữ liệu, khóa ngoại, chiến lược di trú phiên bản và sao lưu/khôi phục.
2. Chốt tiêu chuẩn API: phân trang, mã lỗi, định dạng thời gian, tiền tệ VND, mã yêu cầu chống ghi trùng, phân quyền và nhật ký.
3. Kiểm thử thực tế đăng nhập, phân quyền từng vai trò, đổi/thu hồi phiên đăng nhập, khóa tài khoản.
4. Kiểm thử dữ liệu đồng thời và phục hồi sau mất điện; cân nhắc PostgreSQL khi triển khai nhiều người dùng.
5. Cấu hình HTTPS, bí mật môi trường, CORS, giám sát, cảnh báo và triển khai máy chủ.
6. Đối chiếu từng chức năng trên giao diện V86 với API thật; các nút chưa nối phải ghi rõ.
7. Kiểm thử sao lưu và khôi phục dữ liệu trước khi đưa vào vận hành.

## Tiêu chuẩn chuyển sang phân hệ 02
- Giao diện V86 không bị thay đổi ngoài phạm vi được duyệt.
- Tất cả API nền tảng có kiểm thử xác thực/phân quyền và tình huống lỗi.
- Có biên bản nghiệm thu của kỹ thuật và chủ dự án; không chấp nhận báo cáo chỉ dựa vào số API.

## Chạy tại máy kỹ thuật
`pip install -r requirements.txt`
`export SUNNY_ADMIN_PASSWORD='mat-khau-rieng-it-nhat-12-ky-tu'`
`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765`
`python -m pytest tests -q`

Lưu ý: Đây là giai đoạn nền tảng, **chưa phải ERP hoàn thiện**. AI Agent và kết nối cân/camera chưa được nghiệm thu vận hành thực tế.
