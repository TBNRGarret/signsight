# Luồng đóng góp web

## Người dùng

1. Mở /web/observations.html và đăng nhập.
2. Chọn **Chụp hoặc chọn ảnh**, rồi chụp ảnh hoặc chọn từ thư viện.
3. Hệ thống tự tải ảnh, tạo ảnh xem trước và nhận diện. Chưa tạo biển trên bản đồ ở bước này.
4. Kiểm tra nhãn. Đặt ghim cho từng biển và bấm **Xác nhận vị trí biển này**. GPS/EXIF là vị trí gợi ý; kéo ghim tới biển nếu cần. Có phần nhập tọa độ nâng cao khi bản đồ/GPS không dùng được.
5. Gửi các biển đã chọn. Lịch sử hiển thị ảnh nhỏ, trạng thái và chi tiết.
6. Manager/admin đăng nhập sẽ vào /web/management.html và duyệt trong tab Đóng góp. Khi được duyệt, dùng **Xem trên bản đồ** để mở đúng biển; cookie đăng nhập vẫn dùng chung.

Nếu upload lỗi, thử tải lại ảnh đã chọn. Nếu nhận diện lỗi sau upload, thử nhận diện lại trên ảnh đã lưu. Bấm gửi duyệt chỉ được khi mọi biển được chọn đã có tọa độ hợp lệ và được xác nhận.

## Kiểm thử

TDD có các trường hợp: chọn ảnh tự xử lý một lần, khóa thao tác trùng, retry, logout lúc request đang chạy; tọa độ riêng từng biển, xác nhận ghim, GPS lỗi/callback cũ; trạng thái lịch sử, quyền ảnh nhỏ và liên kết tới đúng bản ghi.

Pytest kiểm tra backend. Node tests kiểm tra trạng thái giao diện. Playwright chạy luồng trình duyệt với FastAPI, database và ảnh tạm; detector là fixture có kiểm soát. Có hai cấu hình desktop và viewport điện thoại Chromium. Provider nền bản đồ bên ngoài được stub trong browser tests để CI không phụ thuộc mạng/provider.

Checkpoint thật được smoke-test riêng với database tạm; test pipeline đạt không chứng minh chất lượng ảnh đường phố. Chưa nghiệm thu camera/GPS trên Safari hoặc điện thoại thật.

## Phạm vi sau

Thêm biển thủ công khi AI không phát hiện, bản nháp phục hồi, catalog taxonomy động và timeout/idempotency toàn bộ upload là các việc tiếp theo; không thuộc đợt cải thiện giao diện này.
