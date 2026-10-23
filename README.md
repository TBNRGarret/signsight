# SignSight

Web responsive để đóng góp ảnh và quản lý bản đồ biển báo giao thông. Backend FastAPI phục vụ cả API lẫn frontend HTML/CSS/JavaScript trong một server.

Hướng dẫn [đóng góp ảnh và xem biển được duyệt](docs/contribution_flow.md).

Luồng chính: **chụp/upload ảnh → YOLO phát hiện → người dùng xác nhận nhãn và tọa độ → gửi đóng góp → manager duyệt → biển xuất hiện trên bản đồ**.

## Tính năng

- Đăng ký, đăng nhập dùng chung các trang/tab, tùy chọn ghi nhớ phiên 30 ngày; phân quyền user, manager, admin.
- Upload ảnh, YOLO detection, duyệt đóng góp và xem ảnh bằng chứng.
- MapLibre GL JS với nền vector OpenFreeMap, tìm điểm đến qua Photon, dựng tuyến qua OSRM; lọc biển gần điểm và dọc tuyến.
- Báo cáo thay đổi, đề xuất trùng lặp và yêu cầu xác nhận lại sau thời hạn cấu hình.
- Giao diện điện thoại, light/dark/system theme.
- Notebook EDA và huấn luyện, pipeline chuẩn hóa dữ liệu YOLO.

Bản đồ chỉ hiển thị biển đã được ghi nhận/duyệt trong SignSight. OpenFreeMap cung cấp nền từ dữ liệu OpenStreetMap, không tự bổ sung biển vào database. Database mới sẽ chưa có biển.

## Chạy trên máy mới

Nếu đã có database, ảnh và weights local, xem [cách dùng lại dữ liệu](docs/local_development.md).

Cần Python 3.11; Node.js 24 dùng cho kiểm thử frontend. Clone repo GitHub của bạn rồi chạy từ thư mục gốc.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m backend.manage migrate
.\.venv\Scripts\python.exe -m backend.manage bootstrap-admin --username owner --email owner@example.com
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Bootstrap hỏi mật khẩu và chỉ tạo admin đầu tiên. Có thể đăng ký tài khoản user trên web. Nếu đã có `.venv-yolo`, dùng Python trong môi trường đó thay cho `.venv`.

Linux/macOS:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python -m backend.manage migrate
python -m backend.manage bootstrap-admin --username owner --email owner@example.com
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

| Trang | Địa chỉ |
| --- | --- |
| Bản đồ | http://127.0.0.1:8000/web/index.html |
| Đóng góp ảnh | http://127.0.0.1:8000/web/observations.html |
| Quản lý — manager/admin | http://127.0.0.1:8000/web/management.html |
| API Swagger | http://127.0.0.1:8000/docs |

Không cần frontend dev server hay Docker để thử local. Giữ cùng hostname khi chuyển trang để dùng chung cookie đăng nhập.

## Model và dữ liệu

Weights, dataset gốc, database và ảnh upload không nằm trong Git. App vẫn chạy khi chưa có weights; chức năng YOLO sẽ báo chưa sẵn sàng.

Để bật detection:

```powershell
.\.venv\Scripts\python.exe -m pip install -r ai_engine/requirements-yolo.txt
```

Đặt checkpoint tương thích tại `ai_engine/checkpoints/detection/best.pt`, giữ báo cáo huấn luyện cùng checkpoint, rồi khởi động lại server. Adapter hiện yêu cầu đúng thứ tự taxonomy 10 lớp của project; không thay trực tiếp bằng weights 100 lớp hoặc weights COCO. Xem [ảnh và YOLO](docs/images_and_detection.md).

Baseline dùng GTSRB ROI để kiểm tra pipeline, chưa chứng minh chất lượng ảnh đường phố Việt Nam. Taxonomy là mapping thử nghiệm của dự án, cần rà soát trước khi áp dụng thực tế. Notebook Drive trong bản public dùng `YOUR_DRIVE_FILE_ID`: tự điền ID nguồn bạn có quyền truy cập. Dataset và weights có điều kiện sử dụng riêng, không được phân phối kèm repo này.

## Cấu hình và lưu trữ

Mặc định SQLite ở `backend/signsight.db`, ảnh ở `backend/uploads/images`. Thay đổi bằng `DATABASE_URL` và `SIGNSIGHT_STORAGE_ROOT`; xem [.env.example](.env.example) để biết các giá trị mẫu. **Ứng dụng đọc biến môi trường của process, không tự nạp file `.env`.** Ví dụ PowerShell, đặt trước lệnh migrate và chạy server:

```powershell
$env:SIGNSIGHT_YOLO_DEVICE = 'cpu'
$env:SIGNSIGHT_PLACES_PROVIDER = 'photon'
```

Nền bản đồ, tìm địa điểm và routing cần Internet tới các provider. Trên điện thoại dùng IP LAN của máy chạy backend; GPS cần HTTPS. Xem [thử chụp ảnh](docs/field_capture_quickstart.md) và [HTTPS trên iPhone/iPad](docs/iphone_ipad_testing.md). Thử trên thiết bị thật vẫn là bước nghiệm thu cần thực hiện.

## Cấu trúc

```text
backend/      API, auth, migrations, lưu ảnh và nghiệp vụ
frontend/     Ba trang web, theme và MapLibre vendored
ai_engine/    Inference, chuẩn bị dữ liệu và huấn luyện
data/         Taxonomy và CSV split baseline, không chứa ảnh gốc
notebooks/    EDA và train trên Colab/Kaggle
scripts/      Công cụ dữ liệu, benchmark và chuẩn bị repo public
tests/        Kiểm thử Python và JavaScript
docs/         Hướng dẫn kỹ thuật
.github/      CI và mẫu pull request
```

## Kiểm thử

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
node --test (Get-ChildItem tests/*.test.cjs).FullName
```

Linux/macOS:

```bash
python -m pytest tests -q
node --test tests/*.test.cjs
```

CI chạy các bộ kiểm thử trên CPU, không tải dataset/weights. Kiểm thử checkpoint thật là opt-in; xem [CONTRIBUTING.md](CONTRIBUTING.md).

Tài liệu thêm: [quản lý và backup](docs/web_and_management.md), [đăng nhập/migrations](docs/authentication_setup.md), [pipeline dữ liệu Việt Nam](docs/local_vietnam_pipeline.md), [EDA Drive](docs/drive_dataset_eda.md).

## Đưa lên GitHub

Repo source chính: signsight, nhánh main. Phát triển trực tiếp trong checkout GitHub cố định ngoài cache. Tài liệu môn học giữ riêng; không sao chép lịch sử Git từ thư mục tài liệu vào repo này. Xem [source và dữ liệu local](docs/local_development.md).

Chưa chọn giấy phép cho source code của dự án. MapLibre giữ giấy phép riêng tại [frontend/vendor/maplibre/LICENSE.txt](frontend/vendor/maplibre/LICENSE.txt).

Chi tiết bản đồ và cách build renderer: [MapLibre + OFM](docs/maplibre.md).
