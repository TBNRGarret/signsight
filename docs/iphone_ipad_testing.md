# Thử SignSight trên iPhone và iPad

Muốn thử **chụp ảnh → tự nhận diện YOLO** trước khi cài HTTPS, xem [hướng dẫn thử nhanh trong Wi-Fi](field_capture_quickstart.md). GPS trình duyệt vẫn cần HTTPS theo hướng dẫn bên dưới.

Chọn **Ghi nhớ đăng nhập 30 ngày trên thiết bị này** khi đăng nhập để dùng lại phiên trên Safari và các trang cùng hostname. Không dùng IP làm bằng chứng đăng nhập. Sau cập nhật cookie ngày 20/10, đăng nhập lại một lần để trang quản lý nhận cookie mới; chỉ manager/admin được mở trang đó.

Nếu nền bản đồ xám: bản web từ 20/10 có ô **Nguồn nền bản đồ** ở góc dưới phải. Chọn **OpenStreetMap · dự phòng** để dùng máy chủ `tile.openstreetmap.de`; nguồn chính lỗi hoàn toàn hoặc chậm quá 10 giây sẽ tự thử nguồn dự phòng một lần. Cả hai vẫn cần Internet. Tải lại trang để nhận bản JavaScript mới. Nguồn dự phòng do [OSM Deutschland/FOSSGIS](https://openstreetmap.de/nutzen/dienste-osm-de/) cung cấp, bản đồ có thể hiển thị thêm tên tiếng Đức.

Nguồn được chọn hoặc tải thành công được lưu trong trình duyệt 24 giờ, nên lần mở sau dùng ngay nguồn đó. Nếu nguồn đã nhớ bị lỗi, hệ thống thử nguồn còn lại một lần; không chuyển qua lại vô hạn. Khi storage bị chặn, bản đồ vẫn chạy nhưng không ghi nhớ lựa chọn.

Cập nhật 14/10/2026. Dùng Safari trên thiết bị cùng Wi-Fi với máy Windows chạy backend. Web responsive đã được thử bằng viewport giả lập; camera, GPS, chứng chỉ và thao tác trên iPhone/iPad thật **chưa được nghiệm thu**. Hướng dẫn này chạy một database/kho ảnh riêng để thử với checkpoint YOLO thật.

## Chuẩn bị trên máy Windows

Máy hiện chưa tìm thấy `mkcert` trong PATH. Cài bản Windows từ [dự án mkcert](https://github.com/FiloSottile/mkcert#installation), mở lại PowerShell rồi kiểm tra `mkcert -version`. Xác định IPv4 của Wi-Fi bằng `ipconfig`; bỏ qua adapter VPN/WSL và thay IP ví dụ dưới đây bằng IP của máy.

Tại thư mục gốc project:

```powershell
$demoIp = '192.168.1.10' # Thay bằng IPv4 Wi-Fi của máy Windows.
New-Item -ItemType Directory -Path backend/certs -Force | Out-Null

# Lệnh này cài CA phát triển vào kho tin cậy trên máy Windows.
mkcert -install
mkcert -key-file backend/certs/key.pem -cert-file backend/certs/cert.pem $demoIp localhost 127.0.0.1

# Xem thư mục chứa CA để chép riêng rootCA.pem sang thiết bị.
mkcert -CAROOT
```

Chỉ chép `rootCA.pem`. Giữ `rootCA-key.pem` và `backend/certs/key.pem` trên máy Windows; không gửi chúng sang điện thoại hay commit vào Git. CA này dành cho thiết bị của nhóm khi thử local. [Tài liệu mkcert về thiết bị di động](https://github.com/FiloSottile/mkcert#mobile-devices).

Trong **terminal riêng**, tạo môi trường thử để các biến dưới đây không ảnh hưởng phiên server khác:

```powershell
New-Item -ItemType Directory -Path .cache/iphone_demo -Force | Out-Null
$demoDbPath = Join-Path (Get-Location).Path '.cache/iphone_demo/signsight.db'
$env:DATABASE_URL = 'sqlite:///' + $demoDbPath.Replace('\', '/')
$env:SIGNSIGHT_STORAGE_ROOT = Join-Path (Get-Location).Path '.cache/iphone_demo/images'
$env:SIGNSIGHT_YOLO_DEVICE = '0' # Máy hiện có CUDA; dùng 'cpu' nếu không dùng GPU.

.\.venv-yolo\Scripts\python.exe -m backend.manage migrate
# Chỉ chạy bootstrap lần đầu; tự nhập mật khẩu khi được hỏi.
.\.venv-yolo\Scripts\python.exe -m backend.manage bootstrap-admin --username qa_owner --email qa_owner@example.com
.\.venv-yolo\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile backend/certs/key.pem --ssl-certfile backend/certs/cert.pem
```

Giữ terminal chạy. Nếu Windows hỏi về quyền truy cập mạng, cho phép trên mạng riêng đang dùng để thử. Database mới ban đầu không có biển; đóng góp và duyệt một biển trước khi thử chi tiết/nearby. Phiên `127.0.0.1:8000` hiện có, nếu đang chạy, không phục vụ điện thoại.

## Cài chứng chỉ trên iPhone/iPad

1. Chép **chứng chỉ công khai** `rootCA.pem` vào thiết bị rồi mở nó. Cài hồ sơ tại **Settings → Profile Downloaded**; nếu mục này không hiện, kiểm tra **Settings → General → VPN & Device Management**.
2. Sau khi cài, mở **Settings → General → About → Certificate Trust Settings**, bật tin cậy cho đúng CA phát triển vừa cài. Cài hồ sơ bằng tay chưa tự bật tin cậy SSL/TLS. [Hướng dẫn Apple](https://support.apple.com/en-us/102390).
3. Trong Safari, mở `https://192.168.1.10:8443/web/index.html`, thay IP thật. Không dùng `localhost` hoặc `127.0.0.1` trên thiết bị.
4. Chỉ tiếp tục khi không có cảnh báo chứng chỉ. Nếu IP Wi-Fi của máy đổi, tạo lại cert cho IP mới; nếu vẫn không kết nối, kiểm tra Wi-Fi cùng mạng, VPN, cô lập thiết bị của router và cổng 8443 trên Windows.

Khi kết thúc thử, dừng server bằng Ctrl+C và đóng terminal riêng. Có thể gỡ hồ sơ CA phát triển khỏi thiết bị khi không còn dùng. Những lệnh cài CA và các bước trên thiết bị trong tài liệu này chưa được thực hiện tự động.

## Chạy ba luồng trên Safari

Ghi loại máy, phiên bản iOS/iPadOS, kích thước/orientation, mạng và kết quả thực tế. Đăng nhập một lần trên Safari dùng chung trang bản đồ/ảnh/quản lý và các tab trong cùng hostname; reload không cần đăng nhập lại nếu cookie còn hạn (mặc định 8 giờ). Kiểm tra cả logout ở một tab rồi quay lại tab khác. Tài khoản đăng ký trên điện thoại là user, tài khoản `qa_owner` trên máy tính dùng để duyệt; điện thoại và máy tính giữ phiên riêng.

| # | Bước | Mong đợi | Kết quả thực tế |
| --- | --- | --- | --- |
| 1 | Mở HTTPS, đăng ký user | Không cảnh báo cert; đăng nhập thành công; map có tiles | Chưa chạy |
| 2 | Bấm “Vị trí của tôi”, cho phép vị trí | Map tới vị trí thật và hiện độ chính xác | Chưa chạy |
| 3 | Từ chối vị trí rồi chạm map | Có thông báo; vẫn chọn điểm được | Chưa chạy |
| 4 | Mở observations; bấm chọn ảnh → chụp ảnh nếu Safari cung cấp tùy chọn | Camera mở; kiểm tra chọn camera sau; ảnh upload được | Chưa chạy |
| 5 | Bấm YOLO và điền GPS cho từng biển | Có thẻ kết quả hoặc thông báo không tìm thấy; user xác nhận tọa độ biển trước khi gửi | Chưa chạy |
| 6 | Gửi đóng góp; máy tính đăng nhập `qa_owner` để duyệt | Pending → accepted; biển có ảnh bằng chứng trên map và lịch sử | Chưa chạy |
| 7 | Tìm Nguyễn Huệ hoặc Bến Thành; chọn điểm đến; dựng tuyến | TP.HCM được ưu tiên; tuyến và danh sách biển gần tuyến hiện | Chưa chạy |
| 8 | Nearby quanh điểm chạm; đổi 100/300/1.000 m | Danh sách thay đổi theo bán kính | Chưa chạy |
| 9 | Mở chi tiết; gửi report kèm ảnh; manager duyệt | Trạng thái báo cáo và ảnh cập nhật đúng | Chưa chạy |
| 10 | Thử record quá hạn bằng fixture thời gian riêng | Hiện cần xác nhận; chỉ report được duyệt mới gia hạn | Chưa chạy |
| 11 | Xoay dọc/ngang iPhone và iPad | Map đủ rộng, tiles không bị xám, form không tràn ngang | Chưa chạy |
| 12 | Tắt mạng lúc upload/gửi report rồi thử lại | Hiện lỗi rõ ràng; kiểm tra giữ nội dung và không gửi trùng | Chưa chạy |
| 13 | Đăng xuất | Dữ liệu cá nhân bị xóa khỏi giao diện; thao tác có quyền bị khóa | Chưa chạy |

Input ảnh hiện nhận JPEG, PNG và WebP; nếu chọn ảnh HEIC/HEIF từ thư viện mà upload bị từ chối, dùng một bản JPEG để tiếp tục và ghi nhận trường hợp đó. Không coi ảnh crop GTSRB hoặc ảnh tổng hợp dùng trong benchmark là bằng chứng chất lượng detection ngoài đường. GPS là vị trí người chụp; cần xác nhận vị trí của từng biển.

Không chỉnh ngày giờ của máy hoặc hạn record đang dùng để giả lập quá hạn. Dùng DB thử riêng và fixture như QA Alpha (tài liệu nội bộ, không kèm bản public). Kết quả trên thiết bị cần ghi Pass/Fail/Blocked theo từng dòng; chưa thử thì giữ “Chưa chạy”.
