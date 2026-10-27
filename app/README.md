# SUNNY AI FLEX 3D ERP

Bản triển khai theo tài liệu SUNNY ERP AI Implementation 001 phiên bản 1.1 ngày 25/10/2026. Gói này có mã nguồn backend, React, migration, bản giao diện đã build và kiểm thử. ERP chạy được khi chưa có API key OpenAI.

Phiên bản 2.2 gồm bộ cài đi kèm môi trường chạy Windows x86_64 và Linux x86_64. Trong thư mục gốc bộ cài, mở `CAI_DAT_WINDOWS.cmd` để cài riêng cho tài khoản Windows và tạo biểu tượng Desktop, hoặc `MO_SUNNY_ERP.cmd` để chạy trực tiếp. Linux dùng `bash MO_LINUX.sh`. Các cách này không yêu cầu cài Python/Node.js hoặc tải thư viện từ Internet để dùng ERP.

Bảng điều khiển tại máy chủ cho phép tạo quản trị lần đầu, mở/dừng máy chủ, bật Wi-Fi nội bộ, sao lưu đầy đủ database/chứng từ và khôi phục sang thư mục dữ liệu mới. Dữ liệu nằm riêng ngoài thư mục chương trình. Bảng điều khiển chỉ lắng nghe loopback, có phiên ngẫu nhiên riêng, kiểm tra Host/Origin/CSRF và khóa chống mở hai tiến trình cùng thư mục dữ liệu. Khôi phục giữ lại dữ liệu cũ, tạo bản an toàn và thu hồi các phiên đăng nhập.

Hướng dẫn vận hành dành cho người sử dụng nằm trong `docs/current/HUONG_DAN_SU_DUNG.md`. Các lệnh cài từ mã nguồn dưới đây dành cho kỹ thuật phát triển hoặc triển khai riêng.

Điểm chạy hiện tại là `backend.app.main:app`. Các file `backend/main.py`, `public/` và hồ sơ trong `archive/previous_handoffs/` được giữ để kiểm thử hồi quy của bản cũ; chúng không phải giao diện được phục vụ bởi bản ERP hiện tại.

## Chạy từ mã nguồn trên Windows

1. Cài Python 3.12 và giải nén toàn bộ gói vào một thư mục.
2. Mở `CHAY_WINDOWS.bat`. Lần đầu cần Internet để cài thư viện. Chương trình tạo cấu hình riêng và hỏi tài khoản quản trị cùng mật khẩu tối thiểu 12 ký tự.
3. Trình duyệt tự mở sau khi máy chủ sẵn sàng tại `http://127.0.0.1:8765`. Đăng nhập và đổi mật khẩu lần đầu.

Giao diện đã build sẵn, nên người sử dụng không cần cài Node.js. Không nhập API key vào giao diện ERP. Tệp cấu hình riêng không được đưa vào gói mã nguồn hay Git.

## Chạy bằng dòng lệnh

Thực hiện tại thư mục gốc dự án:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m backend.scripts.setup_local
.venv/bin/python -m backend.scripts.run_server
```

Trên Windows, thay `.venv/bin/python` bằng `.venv\Scripts\python.exe`. Có thể dùng `bash CHAY_ERP.sh` trên Linux.

Để điện thoại cùng Wi-Fi truy cập máy chủ trong xưởng, kỹ thuật chạy `run_server --host 0.0.0.0` rồi mở địa chỉ IP nội bộ của máy chủ với cổng 8765. Việc công bố ra Internet cần cấu hình HTTPS và hạ tầng riêng; gói này chưa được triển khai lên máy chủ của Sunny.

## Cấu trúc và tài liệu kỹ thuật

- `backend/app/`: xác thực, phạm vi dữ liệu, model SQLAlchemy, DTO, nghiệp vụ và API hiện tại.
- `backend/alembic/`: bảy migration có phiên bản; migration đầu có snapshot DDL để không phụ thuộc thay đổi model về sau.
- `frontend/src/`: React 18, TypeScript, Zustand, TanStack Query và TailwindCSS.
- `frontend/dist/`: giao diện đã build để FastAPI phục vụ trực tiếp.
- `tests/current/`: kiểm thử theo đặc tả mới; các kiểm thử còn lại giữ hồi quy bản cũ.
- `docs/current/openapi.json`: hợp đồng API thực tế, gồm kiểu phản hồi, Bearer JWT, lỗi và Idempotency-Key.
- `docs/current/schema.sql`: toàn bộ schema lấy từ cơ sở dữ liệu vừa migrate.
- `docs/current/ERD_44_TABLES.mmd`: quan hệ và PK/FK của 44 bảng baseline; các UNIQUE ghép, CHECK và index nằm đầy đủ trong SQL.
- `docs/current/SCREEN_MAP.md`: ánh xạ 40 màn hình và thao tác theo tài liệu.
- `docs/current/ACCEPTANCE.md`: bằng chứng kiểm thử và các phần cần nghiệm thu ở môi trường thực tế.

Tài liệu API mở tại `/api/docs`; toàn bộ tài nguyên Swagger được phục vụ trong gói, không phụ thuộc CDN. Nút Authorize nhận access token ERP lấy từ `/api/v1/auth/login`, không nhận API key OpenAI.

## Dữ liệu và migration

Có 44 bảng baseline và 7 bảng hỗ trợ được bổ sung có lý do cụ thể:

| Bảng bổ sung | Mục đích |
| --- | --- |
| auth_sessions | Xoay vòng refresh token, thu hồi phiên và phát hiện dùng lại token cũ |
| operation_keys | Chống gửi lặp cùng giao dịch và phát hiện cùng khóa nhưng khác nội dung |
| supplier_payment_allocations | Phân bổ một khoản chi cho một hoặc nhiều hóa đơn nhà cung cấp theo điểm 6 của tài liệu |
| payment_allocation_events | Giữ lịch sử tăng từng lần gạch nợ, đối soát cache và tính báo cáo tại ngày chốt |
| ai_conversations | Lịch sử hội thoại riêng của người sử dụng theo điểm 11 |
| ai_messages | Nội dung, nguồn dữ liệu, trạng thái và số token từng lượt chat |
| production_report_corrections | Đính chính bằng sự kiện mới, giữ nguyên báo cáo sản xuất gốc |

SQLite bật FOREIGN KEY trên từng kết nối, WAL và busy timeout. Giao dịch ghi sổ dùng khóa ghi trước khi kiểm tra số dư. Số tiền là INTEGER VNĐ. Số lượng theo hợp đồng DECIMAL(18,6), được lưu chính xác bằng số nguyên phần triệu trong SQLite và chuyển thành Decimal qua SQLAlchemy; API trả số lượng dạng chuỗi thập phân. Không đọc trực tiếp cột số lượng vật lý như số lượng thực.

Thời điểm lưu UTC. Múi giờ chốt ngày mặc định là `Asia/Ho_Chi_Minh` (UTC+7, cùng giờ với Lào), có thể cấu hình `SUNNY_BUSINESS_TIMEZONE`. Báo cáo ngày, biên thời gian gạch nợ và KPI chuyển ngày địa phương sang UTC; Windows đi kèm gói tzdata. Giao diện lấy ngày kinh doanh từ máy chủ.

```bash
.venv/bin/python -m backend.scripts.migrate_db --database runtime/database/sunny.sqlite3
.venv/bin/python -m backend.scripts.check_db_integrity --database runtime/database/sunny.sqlite3
```

Mỗi lần nâng cấp cơ sở dữ liệu có sẵn đều tạo bản sao lưu nhất quán trước. Schema cũ không tương thích sẽ bị từ chối; không xóa bảng hoặc tự gán dữ liệu sang tenant. Gói nguồn được cung cấp không có database sản xuất thực tế của Sunny, nên việc chuyển dữ liệu sản xuất cũ chưa được xác minh trên dữ liệu thật.

## Quy ước nghiệp vụ đã thực thi

- CTV được lọc theo `employees.id`, không dùng nhầm ID tài khoản. Các khóa ngoại được kiểm tra cùng tổ chức, và cơ sở hoặc quyền sở hữu được kiểm tra ở backend.
- Tiền dòng hàng làm tròn HALF UP đến 1 VNĐ. Doanh thu và KPI doanh thu lấy tiền hóa đơn trước VAT; công nợ dùng tổng phải thanh toán gồm VAT.
- Công nợ được tính từ hóa đơn và lịch sử phân bổ, có đối soát và API tái tính cache. Tiền khách trả trước chưa phân bổ không bị tự coi là hóa đơn đã thanh toán.
- Kho ghi thẻ kho bất biến. Bút toán không được sửa/xóa. Phiếu giao, nhận hàng, điều chuyển và nghiệp vụ tiền dùng `Idempotency-Key` từ 8 đến 120 ký tự. Gửi lại cùng khóa và nội dung nhận lại kết quả cũ; thay nội dung hoặc người thực hiện bị từ chối.
- Điều chuyển nguyên cuộn giữ mã cuộn. Điều chuyển một phần tạo đơn vị con để truy vết phần đã tách. Hàng đang vận chuyển được báo cáo riêng.
- Phát hành lệnh sản xuất xuất nguyên vật liệu theo BOM đã chọn. Công đoạn cuối quyết định sản lượng thành phẩm, các công đoạn trung gian không bị cộng trùng.
- Giá vốn nhập thành phẩm lấy từ giá trị nguyên liệu thực tế đã xuất chia cho sản lượng đạt. Sai số làm tròn đơn giá nguyên VNĐ được lưu trong audit. Đây là giá vốn nguyên liệu; lương và phân bổ chi phí chung chưa có mô hình trong baseline.
- Đính chính sản lượng chỉ cho ADMIN hoặc QC_LEADER, trước khi ghi sổ hoàn tất và khi công đoạn tiếp theo chưa có số liệu. Dữ liệu gốc được giữ nguyên. Các giao dịch kho gắn chứng từ nguồn không được đảo riêng để làm lệch trạng thái chứng từ.
- KPI sản lượng và tỷ lệ phế phẩm đo theo m2 tại công đoạn cuối; KPI tiền và KPI tỷ lệ có đơn vị riêng. KPI năm kỳ được lọc theo ngày bắt đầu và kết thúc của kỳ.
- Tổng phế phẩm của lệnh gồm hao hụt ở mọi công đoạn. Công đoạn sau chỉ nhận lượng đạt của công đoạn trước; công đoạn không còn đầu vào được đóng có audit và không tạo báo cáo hay tồn thành phẩm giả. Nếu toàn bộ thành phế phẩm, chi phí nguyên liệu được ghi là tổn thất, tách khỏi sai số làm tròn.
- Phân quyền kết hợp từng vai trò với đúng phạm vi cơ sở của vai trò đó; gán thêm một vai trò toàn tổ chức không tự mở rộng vai trò cơ sở khác.
- Đổi người nhận việc giữ lịch sử và thu hồi quyền từ phân công cũ. Chi tiết hóa đơn/phiếu tiền hiển thị các lần phân bổ và số dư còn lại.
- Danh sách có bộ lọc và sắp xếp ở máy chủ; trạng thái, thứ tự và trang được giữ trên URL khi quay lại. Sửa thông tin đầu chứng từ giữ ID dòng không thay đổi.
- Trang cá nhân xem và thu hồi các phiên đang hoạt động. Giới hạn mặc định 8 phiên/tài khoản, đặt bằng `SUNNY_MAX_SESSIONS` (1–100); xoay refresh token không tạo thêm thiết bị.
- Công nhân chỉ thực hiện và báo cáo lệnh được liên kết với công việc đã giao cho mình.

## SUNNY AI và cảnh báo

Theo yêu cầu của Sunny, việc cấu hình API key được để sau. Các phân hệ ERP vẫn chạy. Bảng chat hiện thông báo chờ cấu hình và API chat trả 503 rõ ràng; không tạo câu trả lời giả.

Phần tích hợp server đã có allowlist công cụ, kiểm tra lại quyền trước từng công cụ, lịch sử riêng, SSE, ngắt kết nối, timeout, giới hạn độ dài và ghi số token. Các kiểm thử AI dùng provider dành riêng cho kiểm thử. Chưa gọi OpenAI thật, chưa xác minh hạn mức, chi phí hoặc chất lượng trả lời thực tế của tài khoản Sunny.

Tác vụ cảnh báo chạy mặc định mỗi 300 giây. KPI được đối chiếu từ dữ liệu thật và thông báo có nguồn, ngưỡng cùng chống trùng trong 24 giờ. Cảnh báo nhập kho tăng vọt chỉ chạy cho SKU đã cấu hình ngưỡng riêng để tránh so sánh lẫn kg, m và m2. Ví dụ cấu hình:

```text
SUNNY_RECEIPT_SPIKE_THRESHOLDS={"PP":{"minimum_quantity":100,"factor":3,"baseline_days":14}}
```

Báo cáo dự kiến dòng tiền chỉ dựa trên AR/AP có hạn chứng từ. Báo cáo ghi rõ chưa có số dư tiền đầu kỳ, lương và các khoản chi chưa được mô hình hóa.

## Sao lưu và khôi phục

```bash
.venv/bin/python -m backend.scripts.backup_db
.venv/bin/python -m backend.scripts.restore_db --backup /duong/dan/backup.sqlite3 --target /duong/dan/moi/restored.sqlite3
.venv/bin/python -m backend.scripts.check_db_integrity --database /duong/dan/moi/restored.sqlite3
```

Khôi phục vào đường dẫn mới, kiểm tra xong mới chuyển cấu hình máy chủ sang bản phục hồi. Công cụ không ghi đè database đang chạy. Sao lưu SQLite bằng API backup, không chép riêng file DB khi WAL còn hoạt động. Tệp đính kèm trong thư mục uploads cần được sao lưu cùng phiên dữ liệu; cấu hình chứa bí mật cần được giữ riêng. Có thể giữ 7 bản hằng ngày và 4 bản hằng tuần theo quy trình vận hành của doanh nghiệp; các lệnh CLI này không tự xóa bản cũ. Bảng điều khiển 2.2 quản lý riêng bảy bản sao lưu tự động gần nhất; bản thủ công được giữ lại.

## Kiểm thử và build lại

```bash
.venv/bin/python -m pytest tests -q
cd frontend
npm ci
npm run lint
npm run build
node tests/browser_acceptance.mjs
node tests/full_workflow_acceptance.mjs
node tests/desktop_acceptance.mjs
node tests/completeness_acceptance.mjs
```

Lần đầu chạy kiểm thử trình duyệt cần `npx playwright install chromium`. Bộ kiểm thử tự tạo database QA mới, không mở database sản xuất. Kết quả backend, trình duyệt và đối soát nằm trong `docs/current/`.

```bash
.venv/bin/python -m backend.scripts.export_contract --output docs/current
.venv/bin/python deploy/verify_release.py
```

Dockerfile và Compose đã trỏ về ứng dụng hiện tại. Nếu dùng Docker, cấp biến môi trường riêng và tạo admin bằng `backend.scripts.create_admin` trong container. Việc chạy Docker, HTTPS, Windows và thiết bị thật chưa được nghiệm thu trong môi trường khách hàng.

Hóa đơn điện tử pháp lý, bảng lương, đa tiền tệ, OCR sản xuất, camera, cân và QR phần cứng chưa nằm trong phần nghiệm thu của bản baseline này. Không gộp các module cũ chưa kiểm chứng vào danh sách chức năng đã hoàn thành của ứng dụng mới.
