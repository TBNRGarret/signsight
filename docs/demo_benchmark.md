# Đo thời gian xử lý demo

Script `scripts/benchmark_demo.py` đo checkpoint YOLO hiện có và API local qua HTTP loopback thật. Mỗi lượt tự tạo SQLite, kho ảnh và tài khoản tạm, chạy server ở cổng trống trên `127.0.0.1`, rồi đóng server và dọn dữ liệu tạm. Không dùng server, thông tin đăng nhập hay database của project.

## Chạy lại

Từ thư mục gốc, dùng interpreter đã cài runtime YOLO:

```powershell
# CPU; thay ảnh bằng một ảnh JPEG/PNG/WebP muốn đo.
.\.venv-yolo\Scripts\python.exe -m scripts.benchmark_demo --image archive/Test/11052.png --device cpu --samples 20 --warmup 3 --output runs/benchmarks/cpu_01.json

# GPU trên máy hiện tại; --device 0 là CUDA GPU đầu tiên.
.\.venv-yolo\Scripts\python.exe -m scripts.benchmark_demo --image archive/Test/11052.png --device 0 --samples 20 --warmup 3 --output runs/benchmarks/gpu_01.json
```

Lặp `--image <path>` để đo nhiều kích thước trong một lượt. Có thể đổi `--weights` và `--confidence` (mặc định 0,65). Mỗi output cần tên mới; script từ chối ghi đè báo cáo cũ. Dữ liệu thô và p50/p95 được lưu trong JSON cùng phiên bản runtime, hash checkpoint/ảnh và thiết bị thực thi. Nếu thiếu hoặc sai checkpoint/dependencies, lượt đo dừng; không thay YOLO bằng CNN.

Đối với ảnh đường phố, dùng ảnh có quyền sử dụng. JSON chỉ ghi tên file, hash, kích thước và số detection; không lưu ảnh hoặc token. Cùng một ảnh được nhận diện lặp lại để đo thời gian, không tính các lần lặp đó là nhiều mẫu đánh giá chất lượng.

## Các phép đo

- `model_load_ms`: thời gian adapter nạp/kiểm tra weights sau khi server đã sẵn sàng. Không gồm khởi động Python/server hoặc tải CNN baseline.
- `first_detect_ms`: request YOLO đầu tiên của mỗi ảnh. Ảnh đầu tiên bao gồm khởi tạo predictor; các ảnh sau dùng predictor đã có. Hardware probe đã chạy trước đó, nên đây không phải toàn bộ thời gian khởi động ứng dụng.
- `detector_predict`: adapter YOLO trên ảnh RGB đã đọc từ JPEG chuẩn hóa, gồm tiền xử lý/inference/hậu xử lý và chuyển kết quả về CPU. Không gồm HTTP, xác thực, đọc ảnh hay lưu run vào DB.
- `detect_http`: HTTP request tới `/images/{id}/detect`, gồm xác thực, đọc ảnh, nhận diện và lưu run.
- `upload_http`: HTTP upload, chuẩn hóa JPEG, hash và lưu file/metadata.
- `map_http`: `/map/signs` theo bbox, với 5 biển fixture; không gồm tải tiles hay vẽ Leaflet.

Mỗi stage bỏ các lượt warmup trước khi tính thống kê. Các request chạy nối tiếp, concurrency 1. GPU được đồng bộ trước/sau khi đo; thiết bị được kiểm tra từ predictor đang thực thi, vì Ultralytics có thể giữ bản weights CPU riêng. p50/p95 dùng nội suy tuyến tính tại `(n - 1) × percentile`; giữ toàn bộ sample để đối soát.

Không chạy test suite hoặc nhiều benchmark đồng thời khi đo. Ghi tình trạng máy và chạy thêm lượt độc lập nếu cần đánh giá độ biến động. Các số này chưa bao gồm Wi-Fi, HTTPS, Safari, camera/GPS, Nominatim/OSRM hoặc tải cao nhiều user.

Kết quả local đã đo: 14/10/2026 (tài liệu nội bộ, không kèm bản public). Đánh giá ảnh đường phố và chọn confidence theo [giao thức dataset thực địa](field_dataset_protocol.md); thử user flow thật theo [hướng dẫn iPhone/iPad](iphone_ipad_testing.md).
