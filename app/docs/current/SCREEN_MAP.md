# Các màn hình theo tài liệu triển khai

Các màn hình bên dưới dùng dữ liệu và API thật. Màn hình chi tiết và biểu mẫu dùng chung thành phần React để giữ thống nhất việc kiểm tra dữ liệu, quyền, lỗi và chống gửi lặp.

| Số | Màn hình | Đường dẫn hoặc thao tác |
| --- | --- | --- |
| 1 | Đăng nhập | Trang gốc khi chưa đăng nhập |
| 2 | Hồ sơ cá nhân và đổi mật khẩu | `/profile` |
| 3 | Lịch sử chat riêng tư | `/conversations` |
| 4 | Thông báo và đánh dấu đã đọc | `/erp/notifications` |
| 5 | Tổng quan Giám đốc | `/overview` |
| 6 | Tổng quan nhân viên | `/staff` |
| 7 | Nhà máy và cơ sở | `/erp/sites` |
| 8 | Phòng ban | `/erp/departments` |
| 9 | Nhân viên | `/erp/employees` |
| 10 | Tài khoản và khóa hoặc đặt lại mật khẩu | `/erp/users` |
| 11 | Vai trò và phạm vi cơ sở | `/erp/roles` và thao tác gán vai trò trong chi tiết tài khoản |
| 12 | Giao và xem KPI theo năm kỳ | `/kpi` |
| 13 | Sản phẩm và nguyên vật liệu | `/erp/products` |
| 14 | Khách hàng | `/erp/customers` |
| 15 | Chi tiết khách hàng và liên hệ | `/erp/customers/{id}` |
| 16 | Đơn bán | `/erp/sales_orders` |
| 17 | Tạo và sửa đơn bán nháp | `/erp/sales_orders/new` hoặc nút chỉnh sửa trong chi tiết |
| 18 | Giao hàng và xác nhận giao | `/erp/shipments` |
| 19 | Nhà cung cấp | `/erp/suppliers` |
| 20 | Đơn mua | `/erp/purchase_orders` |
| 21 | Nhận hàng từng phần | Nút Nhận hàng trong chi tiết đơn mua đã duyệt |
| 22 | Tổng quan tồn kho và giá trị hàng đang đi | Báo cáo chọn Tồn kho |
| 23 | Vị trí kho | `/erp/warehouse_locations` |
| 24 | Cuộn vật liệu và nhập xuất | `/erp/inventory_units` |
| 25 | Thẻ kho bất biến | `/erp/inventory_movements` |
| 26 | Điều chuyển và xác nhận nhận | `/erp/stock_transfers` |
| 27 | BOM theo phiên bản và kích hoạt | `/erp/bills_of_materials` |
| 28 | Lệnh sản xuất | `/erp/production_orders` |
| 29 | Chi tiết lệnh và công đoạn | `/erp/production_orders/{id}` |
| 30 | Giao diện công nhân trên điện thoại | `/shop-floor` |
| 31 | Hóa đơn bán | `/erp/customer_invoices` |
| 32 | Chi tiết hóa đơn và phát hành | `/erp/customer_invoices/{id}` |
| 33 | Phiếu thu và xác nhận | `/erp/customer_receipts` |
| 34 | Gạch nợ | Nút Gạch nợ trong phiếu thu đã xác nhận |
| 35 | Hóa đơn nhà cung cấp | `/erp/supplier_bills` |
| 36 | Chi tiền và phân bổ cho nhà cung cấp | `/erp/supplier_payments` |
| 37 | Kanban và cập nhật công việc | `/erp/tasks` |
| 38 | Báo cáo quản trị | `/reports` gồm AR, AP, kho, sản xuất và dự kiến dòng tiền theo quyền |
| 39 | Nhật ký có mã truy vết yêu cầu | `/erp/audit_log` |
| 40 | Bảng chat AI dùng chung | Nút SUNNY AI ở góc màn hình; chờ API key để gọi mô hình |

Tài liệu đính kèm có màn hình riêng tại `/documents`. Đính chính sản lượng nằm trong chi tiết báo cáo tại `/erp/production_reports/{id}` và giữ nguyên báo cáo gốc.

Bản 2.2 bổ sung cây phòng ban, quản lý phiên ở trang cá nhân, đổi người nhận việc có lịch sử, số dư/lịch sử phân bổ thanh toán, lọc/sắp xếp/phân trang ở máy chủ và lỗi gắn với trường nhập. Các thao tác được kiểm tra bằng `completeness_acceptance.json`.
