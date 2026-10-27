# Web quản trị SignSight

Cập nhật 27/10/2026. Web dành cho admin/manager; user đã có MVP Flutter với bản đồ, đóng góp, lịch sử và báo cáo. Android có bản debug; nghiệm thu trên điện thoại thật và iOS còn chờ. Web user được giữ để kiểm tra backend trong giai đoạn chuyển tiếp.

## Điểm vào

Đăng nhập tại /web/index.html. Staff tự chuyển tới /web/management.html và mở sẵn Đóng góp chờ duyệt. Link staff cũ /web/observations.html cũng chuyển về quản trị. Server kiểm tra role cho HTML và API.

## Công việc trong một trang

| Tab | Manager | Admin |
|---|---|---|
| Đóng góp | Xem ảnh có bbox, vị trí, nhãn; chấp nhận/từ chối; xem trạng thái đã xử lý | Có |
| Báo cáo | Đối chiếu ảnh mới, thông tin và lịch sử biển trước khi xử lý | Có |
| Nghi trùng | So sánh hai biển và ảnh; gộp/đánh dấu khác nhau | Có |
| Tất cả biển | Tìm mã/tên/ID, lọc trạng thái/xác minh và xem chi tiết | Có |
| Tài khoản | Không | Đổi user/manager, khóa/mở; bảo vệ tài khoản admin |
| Cấu hình | Không | Thời hạn xác nhận và lịch sử cấu hình |

Mỗi tab chỉ tải dữ liệu khi mở. Hàng đợi dùng bảng ngắn và tự chọn dòng đầu để xử lý ở khung bên cạnh. Trong lúc gửi quyết định, khóa cả hai nút để tránh gửi trùng.

Danh mục tra cứu toàn bộ khu vực và trạng thái; mặc định 25 dòng, chọn được 50/100. Tìm kiếm/lọc chạy phía server trước phân trang. Đổi lọc về trang đầu. Desktop giữ bảng cuộn bên trong, bộ lọc và nút chuyển trang trong khung màn hình.

Link Xem vị trí mở bản đồ kiểm tra bản ghi; form báo cáo cá nhân được ẩn cho staff. Trang quản trị không có upload cá nhân, tìm đường hay Báo cáo của tôi.

## Chạy và kiểm tra

Xem [local_development.md](local_development.md). Workspace có source signsight/ và dữ liệu ở thư mục cha dùng scripts/start_signsight.ps1 từ thư mục cha. Không chạy backend legacy.

Test dùng database tạm; browser fixture tạo 65 biển để kiểm tra nhiều trang, không chèn dữ liệu vào DB của người dùng.

- Pytest: role, mọi trạng thái/khu vực, tìm kiếm literal và phân trang giới hạn.
- Node: tải từng tab, race/logout, khóa quyết định và điều hướng bàn phím.
- Playwright: staff login/duyệt tại workspace, catalogue nhiều trang, lọc, kiểm tra vị trí và quyền từng role.

## API bổ sung

- GET /api/v1/manager/summary: số đóng góp/báo cáo/nghi trùng đang chờ và tổng biển.
- GET /api/v1/manager/signs: q, status, verification_status, offset, limit (1–100).
- API duyệt, tài khoản và policy giữ nguyên.
