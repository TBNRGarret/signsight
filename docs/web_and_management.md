# Web người dùng và quản lý dữ liệu — M3/M4

Cập nhật 10/10/2026. Alpha dùng web responsive cho user trên điện thoại; manager/admin dùng các trang quản lý trong `frontend/`. Phần phát triển app native và toolchain riêng đã được dọn khỏi workspace. YOLO train trên Colab/Kaggle, backend đã tích hợp checkpoint YOLO11n local; chạy bằng interpreter `.venv-yolo` theo [hướng dẫn ảnh/YOLO](images_and_detection.md).

## Chạy backend và web

Từ thư mục gốc:

```powershell
python -m backend.manage migrate
# Chỉ bootstrap nếu chưa có admin; nhập mật khẩu khi được hỏi.
python -m backend.manage bootstrap-admin --username owner --email owner@example.com
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

- `/web/index.html`: đăng ký/đăng nhập, bản đồ theo khung nhìn có lọc lớp/trạng thái, biển gần điểm đã chọn, chi tiết biển kèm ảnh bằng chứng, gửi báo cáo/xác nhận kèm ảnh, danh sách biển cần xác nhận và báo cáo của tôi, tìm địa điểm và tuyến OSRM; admin quản lý tài khoản/roles.
- `/web/observations.html`: chọn/upload ảnh, detections, tọa độ từng biển, gửi đóng góp và lịch sử; manager/admin duyệt observations.
- `/web/management.html`: duyệt reports/nghi trùng, đối chiếu ảnh/lịch sử; admin sửa thời hạn và xem audit.

Ở đầu mỗi trang có mục **Giao diện → Theo thiết bị / Sáng / Tối** (20/10/2026). Lựa chọn lưu trong trình duyệt và dùng chung giữa các trang/tab cùng origin, độc lập với tài khoản. Theo thiết bị là mặc định và phản ứng khi thiết bị đổi chế độ; khi web storage bị chặn, vẫn đổi được trong trang hiện tại. Theme đổi màu giao diện, form và controls; ảnh, tiles và màu marker/biển báo giữ nguyên.

Trên máy phát triển mở `http://127.0.0.1:8000/web/index.html`. Điện thoại cùng Wi-Fi dùng IP LAN của máy chạy backend, ví dụ `http://192.168.1.10:8000/web/index.html`; thay IP thật và cho phép cổng 8000 trên mạng thử nghiệm. Frontend dùng API cùng origin. Camera/GPS trên trình duyệt điện thoại cần HTTPS (secure context); qua `http://` với IP LAN, trình duyệt sẽ chặn GPS.

### HTTPS trong mạng LAN để thử trên điện thoại

Dùng [mkcert](https://github.com/FiloSottile/mkcert) để tạo cert do một root CA cục bộ ký. `mkcert -install` thêm CA đó vào kho tin cậy của máy; chỉ làm trên máy phát triển của mình và không chia sẻ file `rootCA-key.pem`.

```powershell
winget install FiloSottile.mkcert
mkcert -install
# Thay 192.168.1.10 bằng IP LAN thật của máy (ipconfig).
mkcert -key-file backend/certs/key.pem -cert-file backend/certs/cert.pem 192.168.1.10 localhost 127.0.0.1
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile backend/certs/key.pem --ssl-certfile backend/certs/cert.pem
```

Trên điện thoại cần tin root CA: chạy `mkcert -CAROOT` để tìm `rootCA.pem`, chép file đó (không chép `rootCA-key.pem`) sang điện thoại rồi cài. Android: Cài đặt → Bảo mật → Mã hóa và thông tin đăng nhập → Cài chứng chỉ CA. iOS: mở file để cài hồ sơ, sau đó bật trong Cài đặt → Cài đặt chung → Giới thiệu → Cài đặt tin cậy chứng nhận. Mở `https://192.168.1.10:8443/web/index.html` và cho phép cổng 8443 trên tường lửa Windows cho mạng riêng. `backend/certs/` không được commit.

Nếu không cài được CA, có thể dùng một tunnel HTTPS tạm (ví dụ `cloudflared tunnel --url http://localhost:8000`). Tunnel đưa trang ra Internet công khai, nên chỉ bật trong lúc thử và dùng tài khoản test.

Lệnh `uvicorn --ssl-*` trên đã được thử ngày 10/10/2026 với một cert tự ký tạm: IP LAN trả 200 khi client tin cert và bị từ chối khi chưa tin. Lượt thử với mkcert trên điện thoại thật chưa thực hiện.

Với iPhone/iPad, dùng [hướng dẫn Safari riêng](iphone_ipad_testing.md): cài hồ sơ CA và bật tin cậy SSL/TLS, chạy bằng `.venv-yolo` với DB/kho ảnh riêng, rồi kiểm tra camera/GPS và ba luồng user. Máy hiện chưa có `mkcert` trong PATH; chứng chỉ và lượt thử trên thiết bị vẫn chờ thực hiện.

## Trạng thái giao diện và công việc tiếp theo

Trang bản đồ đã có các luồng user của Alpha (cập nhật 10/10/2026):

- Đăng ký rồi tự đăng nhập; GPS hoặc chạm bản đồ để chọn điểm.
- Bản đồ tải `GET /map/signs` theo khung nhìn (tối đa 100 biển, báo khi cần phóng to), lọc theo lớp và trạng thái.
- "Biển gần điểm đã chọn" dùng `GET /signs/nearby`, bán kính 100/300/1.000 m.
- Popup mở thẻ chi tiết (`GET /signs/{id}`): trạng thái biển, trạng thái xác minh, hạn xác nhận, ảnh bằng chứng.
- User gửi báo cáo kèm ảnh (`POST /images` rồi `POST /signs/{id}/reports`): xác nhận còn, đã tháo, hư hỏng, sai loại, sai vị trí (lấy điểm user chạm), bổ sung ảnh. Popup không còn gọi `/revalidation` cũ.
- Danh sách "Biển cần xác nhận lại" (`/me/confirmation-requests`) và "Báo cáo của tôi" (`/me/reports`).
- Thẻ ghi nhận thủ công (legacy `/signs/register`) chỉ hiện cho manager/admin.

Còn cần làm: kiểm tra trên điện thoại thật qua HTTPS theo checklist QA (tài liệu nội bộ, không kèm bản public) (camera/GPS thật, xoay màn hình, mất mạng). PWA cài lên màn hình chính là bước bổ sung sau luồng web cơ bản.

GPS là vị trí người quan sát, không tự chứng minh vị trí của tất cả biển trong ảnh. Dữ liệu chỉ công bố/cập nhật sau khi được duyệt. Biển gần tuyến chưa chứng minh áp dụng đúng chiều đi vì chưa có dữ liệu hướng biển. YOLO đã có checkpoint thật ở `ai_engine/checkpoints/detection/best.pt`; chất lượng mới được kiểm chứng trên GTSRB ROI, cần đánh giá thêm ảnh đường phố Việt Nam.

## Reports, hết hạn và nghi trùng

- Report lưu revision lúc gửi. Khi manager chấp nhận, server claim pending và kiểm tra revision trong cùng giao dịch. Report cũ hoặc duyệt lại trả 409; report cũ vẫn pending để manager từ chối/yêu cầu gửi lại.
- Actions: xác nhận còn, bổ sung ảnh, báo tháo/hỏng, sửa loại/vị trí. Chấp nhận tạo evidence thật, confirmation event và audit trước/sau. Sửa loại giữ prediction AI gốc và đánh dấu nhãn cần kiểm tra.
- Job chạy ngay khi startup và mỗi 60 giây: active quá hạn → expired/needs_confirmation. Không xóa biển hoặc coi biển ngoài thực tế mất hiệu lực. Lệnh idempotent: `python -m backend.manage expire-signs`.
- Policy mặc định 30 ngày; `SIGNSIGHT_CONFIRMATION_DAYS` chỉ seed khi chưa có policy trong DB. Admin đổi qua web, áp dụng cho observations mới được duyệt. Biển đã có giữ `confirmation_days`; biển legacy `NULL` giữ policy cũ theo lớp. Đổi cấu hình không âm thầm thay hạn mọi biển.
- Merge yêu cầu manager/admin, cùng lớp, khoảng cách ≤30 m, chưa tháo/gộp. Giữ source trong DB ở trạng thái removed với `merged_into_id`; evidence source vẫn truy cập qua target. Cả hai có audit/revision mới; target không tự gia hạn TTL. Revalidation legacy chặn khôi phục source đã gộp.
- Migration `0004_map_reports_policy` và `0005_duplicate_links` thêm policy/report/audit/revision/liên kết gộp. Backup SQLite tự tạo trước nâng cấp DB có dữ liệu; khi vận hành cần backup kho ảnh cùng DB (xem dưới).

### Sao lưu database và kho ảnh

`python -m backend.manage backup` chỉ chụp database SQLite. Ảnh nằm trong `backend/uploads/images` (hoặc `SIGNSIGHT_STORAGE_ROOT`), DB chỉ giữ đường dẫn và SHA256. Mất kho ảnh thì evidence, report và observation không mở được ảnh, dù DB vẫn còn. Vì vậy luôn sao lưu cả hai ở cùng một thời điểm:

```powershell
# Dừng uvicorn trước để không có upload/duyệt chen giữa hai bước.
python -m backend.manage backup
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
Compress-Archive -Path backend/uploads/images -DestinationPath "backend/backups/images.$stamp.zip"
```

Chép cả file `.sqlite3` vừa tạo và `images.<stamp>.zip` ra ngoài máy (ổ ngoài hoặc Drive của nhóm). Khi khôi phục, dùng một cặp cùng thời điểm. `backend/backups/` không được commit vì chứa dữ liệu và ảnh của người dùng.

## API dùng chung

| Endpoint | Chức năng |
| --- | --- |
| `GET /map/signs` | Bounds/class/status, offset/limit; mặc định bỏ removed |
| `GET /signs/nearby` | Bán kính quanh tọa độ, khoảng cách và phân trang |
| `GET /signs/{id}` / `/history` | Chi tiết/evidence; audit đã duyệt |
| `GET /places/search?q=...` | Tìm kiếm thủ công, cache và giới hạn provider |
| `POST /navigation/route` | Origin/destination/buffer → geometry, distance/duration, biển theo thứ tự |
| `GET /me/confirmation-requests` | Biển cần xác nhận lại |
| `POST /signs/{id}/reports` | Ảnh của user + action/mô tả, correction nếu cần |
| `GET /me/reports` | Lịch sử reports riêng |
| `GET /manager/reports` / `POST /manager/reports/{id}/review` | Hàng đợi và accept/reject |
| `GET /manager/duplicates` / `POST /manager/duplicates/{id}/review` | Hàng đợi và merge/dismiss |
| `GET /policy` / `PATCH /admin/policy` / `GET /admin/policy/history` | Thời hạn và audit cấu hình |

Prefix `/api/v1`, browser dùng cookie HttpOnly và Swagger/CLI dùng Bearer; limit danh sách tối đa 100. Auth/upload/observations mô tả trong [đăng nhập](authentication_setup.md) và [ảnh/YOLO](images_and_detection.md). Mọi quyền được kiểm tra trên server.

## Provider và cấu hình

| Biến | Mặc định |
| --- | --- |
| `SIGNSIGHT_ROUTING_BASE_URL` | `https://router.project-osrm.org` |
| `SIGNSIGHT_PLACES_PROVIDER` | `photon` (hoặc `nominatim`) |
| `SIGNSIGHT_PLACES_BASE_URL` | `https://photon.komoot.io` khi dùng Photon; `https://nominatim.openstreetmap.org` khi chọn Nominatim |
| `SIGNSIGHT_PROVIDER_USER_AGENT` | `SignSight-Research/1.2` |
| `SIGNSIGHT_LIFECYCLE_INTERVAL_SECONDS` | 60 |

Từ 17/10, tìm điểm đến mặc định dùng **Photon** vì Nominatim không truy cập được trong lần thử của người dùng. Photon là dịch vụ geocoding dùng dữ liệu OSM; public server cho phép dự án có lưu lượng hợp lý và không bảo đảm uptime ([tài liệu/điều kiện Photon](https://github.com/komoot/photon#demo-server)). Chỉ tìm khi user submit; cache tối đa 256 query trong một giờ, một request upstream/giây trong một process. Khi deploy đặt User-Agent có liên hệ thực. Nhiều worker cần shared cache/rate limiter hoặc provider riêng. Tiles OSM có attribution, không prefetch/download offline. Tham khảo [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).

Tìm điểm đến ưu tiên TP.HCM: Photon gửi vị trí ưu tiên `lat=10.7769`, `lon=106.7009` theo [Photon API](https://github.com/komoot/photon/blob/master/docs/api-v1.md#location-bias). Nếu chọn Nominatim, gửi `viewbox` quanh vùng đô thị (`106.35,11.15,107.05,10.35`), `bounded=0`, `addressdetails=1` và `accept-language=vi,en`. Một request lấy tối đa 20 ứng viên; backend đưa địa chỉ có thành phố/tỉnh TP.HCM lên đầu, giữ thứ tự provider trong từng nhóm rồi trả tối đa 5 kết quả. Nhận diện dựa trên địa chỉ hành chính, không dựa vào tên cửa hàng/đường. Không khóa tìm kiếm vào TP.HCM hay Việt Nam; thêm tỉnh/thành trong query để tìm điểm đến nơi khác. Cache lưu danh sách đã xếp hạng. Số nhà/POI có thể chưa có trong OSM; kết quả rỗng khác với lỗi kết nối.

Muốn dùng lại Nominatim, đặt `$env:SIGNSIGHT_PLACES_PROVIDER='nominatim'` trước khi chạy backend. Có thể đặt thêm `SIGNSIGHT_PLACES_BASE_URL` cho instance riêng; URL gốc không gồm `/search` hay `/api/`. Để tương thích cấu hình cũ, nếu chỉ đặt `SIGNSIGHT_PLACES_BASE_URL` mà không chọn provider, ứng dụng hiểu đó là Nominatim. Muốn trỏ URL riêng của Photon cần đặt cả hai biến. Không tự gọi Nominatim khi Photon lỗi; lỗi provider trả 502 để user thử lại.

## Kiểm tra và giới hạn

```powershell
python -m pytest tests -q
node --test tests/frontend_auth.test.cjs tests/frontend_routing.test.cjs tests/frontend_management.test.cjs tests/frontend_reports.test.cjs
python scripts/test_end_to_end_flow.py
# Tùy chọn: gửi một truy vấn thật tới mỗi public provider
python -m scripts.check_map_providers
```

Lần chạy 10/10/2026: **136 tests Python pass, 2 skip** (test YOLO thật chỉ chạy khi bật `SIGNSIGHT_TEST_REAL_YOLO`), **21 tests JavaScript pass** trên 4 file. Test `frontend_reports` kiểm tra payload theo từng action, chặn input sai trước khi upload, upload ảnh trước rồi gửi report với image ID đó, và hiện lỗi từ server. Các luồng user đã chạy trên viewport 360 px với DB tạm; xem QA Alpha 10/10 (tài liệu nội bộ, không kèm bản public).

Provider thật đã smoke check một truy vấn: tuyến HCM 67 điểm geometry, 1.543 m, 157 giây; geocoding trả một địa điểm hợp lệ. Chưa kiểm thử thực địa/hiệu năng nhiều người dùng hoặc UI trên điện thoại thật. Jetson, native app, push, offline maps và dữ liệu hướng biển thuộc Beta.

DB workspace đã nâng từ `0003_images_observations` tới `0005_duplicate_links`. Đối soát backup `backend/backups/signsight.20261006T064148Z.ec5c9c55.sqlite3` giữ nguyên mọi cột/dòng cũ: 5 signs, 10 duplicate candidates, 2 confirmation events, 0 users. Có sẵn 7 tham chiếu user không tồn tại (5 signs/2 events); migration không tạo thêm và không tự sửa/xóa chúng. Record mới chịu ràng buộc FK.
