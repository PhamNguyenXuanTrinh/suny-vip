# SUNNY ERP — Hướng dẫn sử dụng bộ cài

## 1. Mở phần mềm

Máy chủ dùng Windows 10/11 64-bit, trình duyệt Edge hoặc Chrome. Bộ cài đi kèm Python và thư viện. Các phân hệ ERP không cần tải thêm thư viện, không cần cài Node.js và không cần API key.

1. Giải nén toàn bộ gói. Không mở chương trình khi nó còn nằm bên trong tệp ZIP.
2. Mở `CAI_DAT_WINDOWS.cmd`. Bộ cài kiểm tra các tệp, cài riêng cho người dùng hiện tại và tạo biểu tượng **SUNNY ERP** trên Desktop. Không cần quyền quản trị Windows.
3. Bảng điều khiển mở trong trình duyệt. Điền tên doanh nghiệp, tài khoản và mật khẩu quản trị 12–128 ký tự. Giữ mật khẩu riêng.
4. Bấm **Tạo tài khoản và mở máy chủ**, sau đó **Mở phần mềm ERP**. Đăng nhập và đổi mật khẩu lần đầu theo yêu cầu.

Cũng có thể mở `MO_SUNNY_ERP.cmd` trong thư mục đã giải nén để chạy trực tiếp. Dữ liệu luôn nằm riêng tại `%LOCALAPPDATA%\SUNNY_GROUP\FLEX3D_ERP`; cài lại mã chương trình không xóa dữ liệu đó. Không chép cùng một database đang hoạt động lên thư mục đồng bộ mạng.

Nếu kỹ thuật dùng máy chủ Linux x86_64 với glibc, bộ này cũng đi kèm môi trường chạy Linux riêng. Mở bằng `bash MO_LINUX.sh`; không cần cài Python, Node.js hoặc tải thư viện. Có thể truyền `--no-browser --data-dir /thu-muc-du-lieu --port 8765` khi triển khai do kỹ thuật quản lý. Giao diện sử dụng và dữ liệu nghiệp vụ giống bản Windows; thư mục dữ liệu mặc định Linux là `~/.local/share/sunny-flex3d-erp`.

## 2. Khai báo ban đầu

Phần mềm bắt đầu bằng dữ liệu trống, ngoài tài khoản quản trị và sáu vai trò hệ thống.

1. Tạo cơ sở/nhà máy, phòng ban, nhân viên và kho.
2. Tạo tài khoản cho từng nhân viên, gán vai trò và phạm vi cơ sở. Nhân viên đổi mật khẩu ở lần đăng nhập đầu.
3. Khai báo sản phẩm và nguyên vật liệu, đơn vị cơ sở và cách theo dõi cuộn/lô. Đánh dấu sản phẩm được mua, được bán hoặc tự sản xuất phù hợp.
4. Kiểm kê vật tư thực tế rồi dùng **Nhập kho** để ghi số dư ban đầu. Nhập đúng kho, số lượng và giá vốn; không nhập số liệu mẫu vào dữ liệu vận hành.
5. Khai báo khách hàng, người phụ trách, nhà cung cấp, công đoạn và máy móc.

Các vai trò là ADMIN, SALES, CTV, ACCOUNTANT, QC_LEADER và WORKER. Quyền được kiểm tra ở máy chủ; CTV chỉ thấy dữ liệu thuộc phạm vi được giao. Không dùng chung một tài khoản cho cả xưởng.

## 3. Luồng mua hàng và kho

- Tạo đơn mua có các dòng hàng → duyệt → nhận hàng một phần hoặc toàn bộ vào kho. Số lượng đã nhận tự cập nhật.
- Xem cuộn/lô và thẻ kho để đối soát. Giao dịch kho đã ghi sổ không được sửa hoặc xóa.
- Tạo phiếu điều chuyển → xuất khỏi kho nguồn → xác nhận nhận tại kho đích. Hàng đang đi được báo riêng.
- Dùng điều chỉnh kho khi kiểm kê có chênh lệch, với quyền quản trị và lý do cụ thể.

## 4. Luồng sản xuất

1. Tạo BOM theo sản phẩm, sản lượng định mức, nguyên vật liệu và hao hụt; kích hoạt phiên bản đã kiểm tra.
2. Tạo lệnh sản xuất, chọn BOM, sản lượng và các công đoạn.
3. Tạo công việc liên kết lệnh, giao cho công nhân. Khi phát hành lệnh, chọn kho nguyên liệu; hệ thống xuất theo BOM nếu đủ tồn.
4. Công nhân mở **Thao tác tại xưởng**, bắt đầu và báo cáo công đoạn được giao: sản lượng đạt, phế phẩm và thời gian dừng.
5. Trưởng ca kiểm tra, đính chính có lý do nếu cần, rồi hoàn tất và nhập thành phẩm vào kho. Công đoạn cuối quyết định sản lượng đạt hoàn thành. Tổng phế phẩm cộng hao hụt ở mọi công đoạn. Công đoạn sau nhận lượng đạt thực tế của công đoạn trước; nếu không còn đầu vào, hệ thống đóng công đoạn đó và lưu lý do. Không tạo thành phẩm khi toàn bộ là phế phẩm.

Giá vốn thành phẩm của bản này là chi phí nguyên vật liệu thực tế đã xuất. Chưa bao gồm lương và phân bổ chi phí chung.

## 5. Luồng bán hàng và công nợ

- Khách hàng → đơn bán và các dòng hàng → xác nhận đơn → phiếu giao → xuất kho → xác nhận đã giao.
- Tạo hóa đơn bán, kiểm tra tổng tiền và phát hành. Đây là chứng từ quản trị nội bộ, không thay thế hóa đơn điện tử pháp lý.
- Tạo phiếu thu, xác nhận đã thu rồi gạch nợ vào hóa đơn đúng khách. Có thể phân bổ nhiều lần trong giới hạn số tiền và công nợ còn lại.
- Phía nhà cung cấp: ghi nhận hóa đơn phải trả, xác nhận phiếu chi và phân bổ thanh toán.
- Xem báo cáo phải thu, phải trả, tồn kho, sản xuất, KPI và dự kiến dòng tiền. Dự kiến dòng tiền chỉ lấy các chứng từ có hạn thanh toán, chưa có số dư đầu kỳ và khoản chi ngoài mô hình.

## 6. Giao việc, tìm kiếm và tài khoản

- Trong chi tiết công việc, người có quyền bấm **Đổi người nhận việc**, chọn nhân viên và ghi lý do. Lịch sử phân công cũ vẫn được giữ; người đã thu hồi không còn quyền dựa trên phân công đó.
- Danh sách có tìm theo tên/mã, lọc trạng thái, bộ lọc bổ sung và sắp xếp bằng tiêu đề cột. Khi mở chi tiết rồi bấm **Danh sách**, bộ lọc và trang cũ được giữ lại.
- Khi nhập sai, thông báo nằm cạnh trường tương ứng. Có thể xóa nội dung của các ô không bắt buộc rồi lưu.
- Trang tài khoản cá nhân hiển thị phiên đang hoạt động và cho thu hồi từng phiên. Mặc định giữ tối đa 8 phiên; kỹ thuật có thể cấu hình giới hạn. Đây là quản lý phiên đăng nhập, không phải nhận diện phần cứng.
- Màn hình phòng ban hiển thị cây cấp trên/cấp dưới và người quản lý. Chi tiết hóa đơn và phiếu thu/chi có lịch sử phân bổ cùng số dư còn lại.

## 7. Điện thoại trong xưởng

Tại Bảng điều khiển trên máy chủ, bật **Cho phép ERP truy cập qua Wi-Fi nội bộ**. Điện thoại cùng mạng mở địa chỉ nội bộ được hiển thị và đăng nhập bằng tài khoản riêng. Máy chủ phải được bật. Nếu chưa kết nối được, kỹ thuật kiểm tra cùng Wi-Fi, IP máy chủ và Windows Firewall. Bảng điều khiển, cấu hình và bản sao lưu chỉ mở tại máy chủ. Không đưa cổng HTTP nội bộ trực tiếp lên Internet.

## 8. Sao lưu và khôi phục

Bấm **Tạo bản sao lưu đầy đủ**. Tệp `.sunnybackup` chứa database và các chứng từ ảnh/PDF đã ghi nhận. Tệp chứa dữ liệu của mọi tổ chức trên máy và mật khẩu đăng nhập đã băm; giữ riêng tư. API key không được đưa vào bản sao lưu. Hãy chép bản sao sang ổ khác; chỉ lưu trên cùng ổ không bảo vệ được khi ổ hỏng.

Khi máy chủ đang mở, phần mềm tự sao lưu mỗi ngày và giữ bảy bản tự động gần nhất. Bản sao thủ công được giữ lại.

Để khôi phục, chọn bản sao trong Bảng điều khiển, nhập `KHOI PHUC` rồi bấm khôi phục. Máy chủ dừng, tạo bản an toàn, kiểm tra checksum, database và chứng từ, khôi phục sang thư mục dữ liệu mới rồi mở lại. Thư mục cũ được giữ nguyên. Các phiên cũ phải đăng nhập lại. Nếu tệp sai, thiếu chứng từ, cấu hình không hợp lệ hoặc sổ nghiệp vụ không đối soát khớp, cấu hình dữ liệu đang dùng không bị thay. Giới hạn mỗi bản sao là 4 GB dữ liệu sau giải nén; phần mềm từ chối tạo bản vượt giới hạn này và kiểm tra dung lượng trống trước khi khôi phục.

## 9. Tắt máy, nâng cấp và hỗ trợ

- Tắt bằng **Đóng SUNNY ERP và dừng máy chủ** trước khi tắt Windows. Đóng tab trình duyệt không tắt máy chủ.
- Mở biểu tượng SUNNY ERP lần nữa sẽ mở Bảng điều khiển hiện có, tránh chạy hai máy chủ cùng một thư mục dữ liệu.
- Trước khi nâng cấp, tạo và chép bản sao lưu ra ngoài máy. Các phiên bản chương trình được cài vào thư mục riêng; dữ liệu giữ nguyên.
- Đóng máy chủ SUNNY ERP cũ trong Bảng điều khiển trước khi mở bản chương trình mới.
- Nhật ký lỗi nằm trong thư mục `logs` dưới thư mục dữ liệu hiển thị trong Bảng điều khiển. Khi báo lỗi, cung cấp thao tác và thời điểm; không gửi mật khẩu hay API key.

AI chờ cấu hình API key theo yêu cầu của Sunny. Camera, cân, OCR, QR phần cứng, hóa đơn điện tử, bảng lương và đa tiền tệ cần triển khai/nghiệm thu riêng; chưa được tính là đã chạy trong bộ này. Bằng chứng và giới hạn môi trường kiểm thử được ghi tại `app/docs/current/ACCEPTANCE.md`.

Múi giờ chốt ngày mặc định là Việt Nam (Asia/Ho_Chi_Minh, cùng UTC+7 với Lào). Thời điểm giao dịch vẫn được lưu UTC; báo cáo công nợ và KPI dùng biên ngày kinh doanh địa phương. Kỹ thuật có thể đặt `SUNNY_BUSINESS_TIMEZONE` trong cấu hình máy chủ nếu cần.
