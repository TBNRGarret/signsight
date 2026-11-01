# Bản đồ MapLibre + OpenFreeMap

SignSight dùng MapLibre GL JS 6.15.0 để hiển thị và OpenFreeMap (OFM) để cung cấp kiểu nền/vector tiles. Không cần API key cho dịch vụ công cộng OFM. Dữ liệu nền bắt nguồn từ OpenStreetMap; biển báo vẫn đến từ database SignSight sau khi được duyệt.

- Bản đồ chính và bản đồ chọn vị trí đóng góp dùng chung renderer.
- Kéo/zoom, xoay và nghiêng bằng thao tác hỗ trợ của thiết bị; nút la bàn đặt lại hướng Bắc. Nút Về TP.HCM đặt lại góc nhìn.
- Chọn OFM Đường phố, Sáng hoặc Tối; kiểu nền được ghi nhớ trên trình duyệt.
- Chạm marker để xem popup. Ghim đóng góp kéo được, nhưng phải xác nhận riêng từng biển.
- Tuyến đường được vẽ lại sau khi đổi kiểu nền; vị trí camera và marker được giữ.
- Khi mạng lỗi, có thông báo và thử tải lại OFM. Không tự chuyển sang máy chủ raster khác.
- Thiết bị cần WebGL. Nếu không khởi tạo được, đăng nhập vẫn hoạt động và có thể dùng phần tọa độ nâng cao khi đóng góp.

## Runtime và build

JavaScript, CSS và module worker được phục vụ từ frontend/vendor/maplibre/, không tải renderer qua CDN.
MapLibre 6 dùng ESM; script build tạo một browser bundle cho frontend hiện tại và cấu hình worker cùng origin.

Sau npm ci, chạy npm run build:maps để tái tạo bundle/CSS/worker từ các dependency đã pin.
Nếu thay đổi dependency/build, cập nhật phiên bản và SHA256 integrity trong cả index.html và observations.html. Test assets kiểm tra SRI và JavaScript MIME của worker.
Giữ LICENSE.txt đi kèm bản phân phối. Không sửa trực tiếp bundle vendor.

Adapter frontend/map.js nhận tọa độ ứng dụng theo [latitude, longitude], rồi chuyển sang [longitude, latitude] của MapLibre ở ranh giới renderer. API backend, Photon và OSRM không thay đổi.

## Kiểm tra

Node tests kiểm tra tọa độ, lifecycle kiểu nền, phục hồi route, retry, storage và WebGL lỗi.
Playwright chạy renderer thật với style/GeoJSON fixture, database tạm và detector giả lập; kiểm tra desktop và viewport điện thoại Chromium.
Kiểm tra mạng OFM thực tế là bước smoke riêng, không phụ thuộc mạng bên ngoài trong CI.
Camera/GPS và hiệu năng Safari trên iPhone thật cần nghiệm thu trên thiết bị.

OFM công cộng không có cam kết SLA; đổi renderer không tự cải thiện kết quả tìm địa chỉ/tuyến đường. Camera/GPS trên điện thoại cần secure context.

Tham khảo: [MapLibre](https://maplibre.org/maplibre-gl-js/docs/), [OFM quick start](https://openfreemap.org/quick_start/), [OFM service](https://openfreemap.org/).
