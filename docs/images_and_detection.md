# Upload, observations và pipeline YOLO

Backend ảnh/observations và YOLO/train đã có. Ngày 07/10/2026 đã tích hợp checkpoint YOLO11n từ Colab vào đường dẫn mặc định của API. Routing, reports và web manager/admin mô tả trong [web và quản lý](web_and_management.md); web user responsive và Jetson còn cần hoàn thiện.

## Khởi chạy

Từ thư mục gốc project:

```powershell
.\.venv-yolo\Scripts\python.exe -m backend.manage migrate
# Chỉ chạy bootstrap nếu chưa có admin; nhập mật khẩu riêng khi được hỏi.
.\.venv-yolo\Scripts\python.exe -m backend.manage bootstrap-admin --username owner --email owner@example.com
.\.venv-yolo\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Web đóng góp/manager: `http://127.0.0.1:8000/web/observations.html`. Đăng nhập, chọn ảnh, upload, bấm **Detect bằng YOLO**, chọn biển và xác nhận tọa độ từng biển rồi gửi. Manager/admin xem ảnh và duyệt; biển đã được chấp nhận xuất hiện trên bản đồ. Có phân trang cho lịch sử và queue. Chọn đúng interpreter `.venv-yolo` khi chạy backend; Python toàn cục chưa được cài runtime YOLO trong lần tích hợp này.

Nếu chưa có môi trường, tạo `.venv-yolo` và cài cả backend lẫn detector:

```powershell
python -m venv --system-site-packages .venv-yolo
.\.venv-yolo\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -r ai_engine/requirements-yolo.txt
```

`GET /api/v1/ai/status` sau khi đăng nhập phải trả `yolo.ready=true`. Model đang tích hợp có SHA256 `3f4fb2a1e8cef3127f2d24f468401b8e734e8bcd0bfb5bada70c76975884cd92`. Checkpoint là file local, không được tải tự động khi gọi detect.

Swagger: `http://127.0.0.1:8000/docs`. Dùng Authorize với tài khoản đã tạo. Đăng ký tài khoản user bằng `POST /api/v1/auth/register`; admin cấp role manager trên web tài khoản.

## Hợp đồng API đã triển khai

Tất cả endpoint dưới đây cần bearer token. Client không được tự gửi confidence, model version hay actor vào observations.

| Endpoint | Kết quả / quyền |
| --- | --- |
| `POST /api/v1/images` | Multipart trường `file`; lưu ảnh, trả image ID, kích thước, SHA256, URL content và GPS gợi ý nếu có. |
| `GET /api/v1/images/{id}` | Metadata; GPS gợi ý chỉ trả cho chủ ảnh. |
| `GET /api/v1/images/{id}/content` | JPEG cần Authorization; không dùng URL ảnh trực tiếp trong `<img>` khi cần bearer. |
| `POST /api/v1/images/{id}/detect` | Chủ ảnh; YOLO trả inference run ID và 0–25 detections, mỗi detection có ID, class, confidence và bbox pixel. |
| `POST /api/v1/images/{id}/classify` | Chủ ảnh; CNN thật cho ảnh đã cắt một biển; bbox=null, task=classification. |
| `GET /api/v1/inference-runs/{id}` | Chủ ảnh hoặc manager của run đã có observation; không công khai các lần inference riêng tư. |
| `GET /api/v1/ai/status` | Tình trạng CNN/YOLO; lý do YOLO thiếu weights/dependencies hoặc sai taxonomy. |
| `POST /api/v1/observations` | Batch 1–25 detections thuộc ảnh của user; từng biển có tọa độ riêng. |
| `GET /api/v1/me/observations` | Lịch sử tài khoản; lọc tùy chọn `status=pending/accepted/rejected`, offset/limit. Tổng và phân trang tính sau khi lọc; không trả đóng góp của user khác. |
| `GET /api/v1/observations/{id}` | Chủ observation hoặc manager/admin. |
| `GET /api/v1/manager/observations` | Manager/admin, lọc status, offset/limit. |
| `POST /api/v1/manager/observations/{id}/review` | Manager/admin, action accept/reject và comment; review lại trả 409. |
| `GET /api/v1/signs/{id}/evidence` | Danh sách evidence của record, hash nội dung và URL cần bearer. |

Ví dụ payload observations sau khi có image/detection IDs do server cấp:

```json
{
  "image_id": "<image-id>",
  "items": [
    {
      "detection_id": "<detection-id>",
      "latitude": 10.7769,
      "longitude": 106.7009,
      "location_source": "user_confirmed",
      "proposed_class": 0,
      "correction_reason": null
    }
  ]
}
```

Nếu sửa class khác AI, phải có lý do. GPS ảnh thường là vị trí camera: user cần kiểm tra vị trí của từng biển. Không suy ra tọa độ biển từ bounding box.

Ảnh chưa gửi chỉ chủ ảnh xem được. Khi có observation, manager/admin có thể xem ảnh để duyệt. Ảnh có ít nhất một observation accepted trở thành evidence mà mọi tài khoản đã đăng nhập có thể xem. Các observation khác và các lần inference khác không vì thế trở thành công khai. Một ảnh minh chứng có thể chứa nhiều vật thể; chọn ảnh phù hợp trước khi gửi.

## Lưu ảnh, provenance và giao dịch

- Chấp nhận JPEG/PNG/WebP tĩnh, xác minh bằng decoder, MIME phải phù hợp. Mặc định tối đa 10 MiB và 16 triệu pixel. Multipart request bị chặn trước khi spool khi vượt giới hạn file cộng 64 KiB overhead; đọc file tiếp tục kiểm tra giới hạn chính xác.
- Sửa EXIF orientation trước inference; lưu JPEG đã bỏ EXIF/ICC/metadata, không giữ file gốc. GPS hợp lệ được tách thành gợi ý riêng. SHA256 và size luôn là của JPEG lưu trên server, không phải URL hoặc UUID.
- Tên file do server tạo, nằm trong kho riêng; uploads không được mount static. Content kiểm tra lại hash trước khi trả và có `Cache-Control: no-store`.
- DB lưu image → inference run → detections → observations. SHA256 checkpoint ghi model version; tọa độ box tham chiếu JPEG đã chuẩn hóa. Predictions gốc không bị sửa khi user đề xuất nhãn khác.
- Submit batch là một giao dịch: một detection đã gửi làm cả batch thất bại 409, không tạo một phần. Manager duyệt chỉ một lần; claim trạng thái, tạo sign/evidence/confirmation event và duplicate candidates cùng giao dịch. Lỗi rollback giữ observation pending. Hai manager duyệt đồng thời chỉ công bố một record.
- Khi user sửa nhãn, record công bố có confidence=0 và is_uncertain=true vì model chưa tính xác suất cho nhãn mới. Confidence AI gốc vẫn nằm ở detection. `verification_status=current` cho biết manager vừa kiểm tra dữ liệu, độc lập với AI uncertainty.
- Record accepted mới giữ chu kỳ xác nhận mặc định 30 ngày. Hết hạn chuyển `verification_status=needs_confirmation`; không có nghĩa biển ngoài đường hết hiệu lực. Confirm lại giữ chu kỳ đã lưu và không tự xóa AI uncertainty. Record cũ giữ policy theo lớp khi `confirmation_days=NULL`.
- Migration `0003_images_observations` thêm 4 bảng và 2 cột SignRecord, có backup SQLite trước nâng cấp; không tự coi tất cả record active cũ là đã xác minh.

Các endpoint quản lý cũ `/signs/register` và `/revalidation/{id}` vẫn dùng được. Trường URL ảnh tùy ý `image_url`/`new_image_url` đã bỏ để ngừng tạo evidence với hash giả; gửi trường đó trả 422. Evidence mới đi qua upload và observations hoặc reports. Workflow cập nhật biển đã có và web quản lý được mô tả trong [web và quản lý](web_and_management.md).

Backup cần giữ cả database và kho ảnh cùng thời điểm. Backup SQLite hiện tại chỉ chụp database; quy trình sao lưu kèm kho ảnh nằm trong [web và quản lý](web_and_management.md#sao-lưu-database-và-kho-ảnh). Demo lưu local; deployment nhiều worker cần kho ảnh dùng chung và giới hạn tải/inference ở ingress.

## Cấu hình

| Biến môi trường | Mặc định |
| --- | --- |
| `SIGNSIGHT_STORAGE_ROOT` | `backend/uploads/images` |
| `SIGNSIGHT_MAX_UPLOAD_BYTES` | 10485760 |
| `SIGNSIGHT_MAX_IMAGE_PIXELS` | 16000000 |
| `SIGNSIGHT_CONFIRMATION_DAYS` | 30, seed policy lần đầu; sau đó admin đổi policy lưu trong DB |
| `SIGNSIGHT_YOLO_WEIGHTS` | `ai_engine/checkpoints/detection/best.pt` |
| `SIGNSIGHT_YOLO_DEVICE` | Ultralytics tự chọn; có thể đặt `0` hoặc `cpu` |
| `SIGNSIGHT_YOLO_CONFIDENCE` | 0,65; giá trị hữu hạn trong khoảng `(0, 1]` |

Restart server sau thay đổi biến môi trường. YOLO nhận biết checkpoint đổi qua mtime/size và reload khi inference/status tiếp theo. Chỉ dùng checkpoint local đáng tin cậy. Checkpoint COCO hoặc sai thứ tự 10 tên lớp bị từ chối. Thiếu weights hoặc thư viện trả 503, không giả lập kết quả bằng CNN.

## Dataset YOLO

`ai_engine/prepare_detection_data.py` đọc CSV đã chia theo track và ROI từ `archive`. Không chia lại ngẫu nhiên. Kiểm tra đường dẫn, taxonomy, ROI, dimensions, track leakage và hash ảnh trùng giữa splits; tạo images/labels, data.yaml và manifest ghi source/track/hash/box. Refuse ghi đè thư mục đã có.

```powershell
# Strict: dừng nếu phát hiện ảnh trùng giữa splits.
python -m ai_engine.prepare_detection_data --output data/yolo_bootstrap/strict

# Dataset hiện tại có trùng nội dung: giữ test, loại bản trùng từ train/val,
# ghi đầy đủ exclusions; không thay CSV/ảnh nguồn.
python -m ai_engine.prepare_detection_data --output data/yolo_bootstrap/full --deduplicate-overlaps

# Smoke subset: dùng output mới, kiểm tra đủ 10 lớp ở cả ba splits.
python -m ai_engine.prepare_detection_data --output data/yolo_bootstrap/smoke --limit-per-class 2

# Kiểm tra dataset và fingerprint; không cần thư viện Ultralytics.
python -m ai_engine.train_detection validate --data data/yolo_bootstrap/full/data.yaml
```

Lần chuyển đổi local: 11.902 train, 2.940 val, 4.890 test, loại 8 ảnh train trùng test theo SHA256. Bảng dữ liệu CNN cũ vẫn có 11.910 train; báo cáo CNN 99,47% là kết quả đã cung cấp, cần đánh giá lại nếu muốn tuyên bố chất lượng trên tập sạch.

ROI max mặc định exclusive, giống cách crop của pipeline CNN cũ. Có `--roi-max-inclusive` nếu convention annotation của nguồn được kiểm tra là inclusive. Convention được ghi trong manifest; không đổi ngầm. GTSRB là ảnh biển Đức đã cắt với context/ROI, không phải dữ liệu nhiều biển trong cảnh đường phố Việt Nam. Mapping nhãn mục tiêu cần kiểm tra bằng mẫu thực địa.

Dataset thực địa có thể dùng cùng layout. Cách chụp, gán nhãn, chia split theo địa điểm, chấm baseline và chọn lại ngưỡng nằm trong [giao thức dataset thực địa](field_dataset_protocol.md).

```text
dataset/
  data.yaml
  images/train/ ... images/val/ ... images/test/
  labels/train/ ... labels/val/ ... labels/test/
```

Tên lớp trong YAML phải đúng 10 mã, đúng thứ tự taxonomy. Mỗi dòng label là `class_id x_center y_center width height` chuẩn hóa 0–1. Nhiều biển dùng nhiều dòng; ảnh nền đã kiểm tra dùng file label rỗng. Validator yêu cầu mọi lớp có mẫu ở từng split, chặn ảnh trùng nội dung, thiếu nhãn và box vượt ảnh. Ngoài kiểm tra hash vẫn cần tự chia theo biển/địa điểm/phiên quay để tránh near-duplicate leakage.

## Train và evaluate

### Google Colab (luồng hiện tại)

Mở [`notebooks/SignSight_YOLO_Colab.ipynb`](../notebooks/SignSight_YOLO_Colab.ipynb) trên Colab và bật GPU T4. Notebook chứa code, taxonomy và các CSV train/val/test của repo đã nén kèm checksum; **không cần upload dataset ZIP**. Nguồn GTSRB giống notebook CNN, mặc định pin phiên bản `meowmeowmeowmeowmeow/gtsrb-german-traffic-sign/versions/1`.

1. Chạy cell cài dependency và cell ghi pipeline/splits.
2. Trong cell cấu hình, đặt **`USE_DRIVE = True`** nếu muốn dùng lại dữ liệu qua các phiên Colab. Chấp nhận mount Drive khi Colab hỏi. Giữ `SOURCE_ID` mặc định cho GTSRB; `RAW_DATASET_DIR = None` để tự tìm/tải nguồn.
3. Chạy cell dataset. Notebook ưu tiên cache YOLO đã chuẩn bị; nếu chưa có, tìm input GTSRB đã gắn trên Kaggle hoặc tải bằng `kagglehub.dataset_download`. Sau đó chuyển ROI sang nhãn YOLO, kiểm tra hash/boxes và loại ảnh trùng giữa splits, giữ nguyên CSV gốc.
4. Kiểm tra labels, train 50 epochs, evaluate val/test và tải ZIP kết quả.

Cache Drive nằm tại `MyDrive/SignSight/yolo_datasets`: một ZIP cùng file metadata/checksum cho mỗi phiên bản dữ liệu. Khi mở runtime mới, notebook kiểm tra và giải nén cache vào ổ local để train, không tải raw dataset hay chuyển ROI lại. Checkpoint/run được giữ tại `MyDrive/SignSight/runs/detection` khi bật Drive; tên run mới có timestamp, không ghi đè kết quả cũ. Nếu giữ `USE_DRIVE = False`, cache và runs chỉ nằm trong runtime, có thể mất khi Colab kết thúc phiên.

Cache key gồm nguồn, nội dung CSV, code converter/validator/cache và taxonomy; đổi đầu vào tạo cache mới. Cache bị hỏng sẽ báo lỗi và giữ nguyên để kiểm tra; chọn thư mục cache mới hoặc xử lý bản hỏng trước khi chạy tiếp. Cache lưu YAML portable; cell dataset tạo YAML runtime với đường dẫn tuyệt đối cho Ultralytics. Tải raw GTSRB lần đầu có thể tốn thời gian và dung lượng hơn ZIP 10 lớp cũ.

Trên Kaggle, bật GPU/Internet và có thể Add Input → GTSRB để dùng dữ liệu có sẵn ở `/kaggle/input`; không mount Google Drive. Dùng Save Version để giữ outputs. Public dataset thường tải được không cần token; nếu Kaggle yêu cầu đăng nhập/consent thì làm theo thông báo. Cách tìm input và cấu hình `KAGGLEHUB_CACHE` dựa trên [tài liệu KaggleHub chính thức](https://github.com/Kaggle/kagglehub).

ZIP kết quả có weights, `detection_report.json`, plots, config, dataset YAML và manifest. Đặt `best.pt` đã đánh giá vào `ai_engine/checkpoints/detection/best.pt`; cài dependency YOLO trên server để sử dụng inference. Notebook classifier cũ vẫn dùng cho CNN và không bị thay thế.

Tạo lại notebook khi sửa pipeline hoặc CSV: `python -m scripts.generate_yolo_notebook`. Công cụ `python -m scripts.package_yolo_dataset --source <dataset> --output <new-file.zip>` vẫn dùng được cho dataset YOLO riêng chạy qua CLI; không ghi đè ZIP đã có. ZIP bootstrap local cũ được giữ nhưng không còn bắt buộc với notebook. Khi dùng raw archive riêng, đặt `RAW_DATASET_DIR` và `SOURCE_ID` phiên bản riêng; converter vẫn yêu cầu ảnh khớp các CSV kèm notebook.

### CLI dùng chung

Thư viện YOLO là dependency tùy chọn. Để giữ PyTorch CUDA hiện có, local có thể dùng venv kế thừa package hệ thống:

```powershell
python -m venv --system-site-packages .venv-yolo
.\.venv-yolo\Scripts\python.exe -m pip install -r ai_engine/requirements-yolo.txt
```

Smoke từ architecture YOLO11n, không tải pretrained weights và không kích hoạt checkpoint:

```powershell
.\.venv-yolo\Scripts\python.exe -m ai_engine.train_detection train --data data/yolo_bootstrap/smoke/data.yaml --model yolo11n.yaml --epochs 1 --imgsz 128 --batch 4 --device 0 --output runs/detection/smoke_01 --smoke
```

Fine-tune từ checkpoint khởi tạo local; có thể dùng `--model yolo11n.pt --allow-download` để cho phép tải weights chính thức:

```powershell
.\.venv-yolo\Scripts\python.exe -m ai_engine.train_detection train --data data/yolo_bootstrap/full/data.yaml --model ai_engine/checkpoints/detection/yolo11n.pt --epochs 50 --imgsz 640 --batch 8 --device 0 --output runs/detection/bootstrap_01

.\.venv-yolo\Scripts\python.exe -m ai_engine.train_detection evaluate --data data/yolo_bootstrap/full/data.yaml --model runs/detection/bootstrap_01/weights/best.pt --imgsz 640 --batch 8 --device 0 --output runs/detection/evaluation_01
```

Máy không có CUDA dùng `--device cpu`; Windows mặc định workers=0. Seed=42, deterministic=true; fliplr/flipud=0 để không đổi nghĩa biển hướng. AMP tắt để tránh kiểm tra AMP tải thêm checkpoint. Output đã tồn tại bị từ chối.

Train chọn best theo validation, sau đó đánh giá riêng val và test. Report `detection_report.json` chứa precision, recall, mAP50, mAP50–95 tổng và theo lớp, SHA256 dataset/checkpoint, config và phiên bản thư viện; Ultralytics lưu confusion matrix/plots. Không dùng accuracy của classifier thay cho metric detector. Smoke report và checkpoint thử không chứng minh chất lượng deployment.

Sau khi đánh giá trên dữ liệu phù hợp, có thể truyền `--activate` cho một lần train để sao chép best.pt vào đường dẫn detector của API. Checkpoint cũ được backup trước replace; smoke run không được activate. Với run đã có, có thể cấu hình `SIGNSIGHT_YOLO_WEIGHTS` trỏ đến checkpoint đó và restart server. Không activate model chỉ vì pipeline chạy thành công.

Checkpoint đang tích hợp: `ai_engine/checkpoints/detection/best.pt`; training report được giữ tại `ai_engine/checkpoints/detection/detection_report.json`. Runtime Ultralytics được pin `8.4.173`, đúng phiên bản train. Run Colab đã train 20 epochs; test trên 4.890 ảnh GTSRB ROI đạt mAP50 99,30% và mAP50–95 94,80%. Xem review checkpoint (tài liệu nội bộ, không kèm bản public) để phân biệt benchmark ảnh crop với chất lượng ảnh đường phố.

API dùng confidence mặc định **0,65**, NMS IoU 0,45 và tối đa 25 detections. Ngưỡng này gần cực đại F1 0,649 trên validation ROI. Khi tích hợp thật, ngưỡng cũ 0,25 tạo detection sai trên ảnh trắng ở confidence 0,323 và ảnh đen ở 0,258. Đây là lựa chọn ban đầu cho baseline hiện tại; cần hiệu chỉnh trên validation full-scene trước khi công nhận chất lượng đường phố. Tăng ngưỡng có thể bỏ sót biển khó; lỗi nhãn confidence cao vẫn còn.

Đổi ngưỡng trước khi khởi động backend nếu cần thử nghiệm, ví dụ `$env:SIGNSIGHT_YOLO_CONFIDENCE = '0.5'`. `/api/v1/ai/status` trả thêm `yolo.confidence_threshold` để xác nhận cấu hình đang dùng. User có thể bỏ chọn detection sai hoặc sửa nhãn trước khi gửi; kết quả chỉ công bố sau khi manager duyệt. Export ONNX/TensorRT, test Jetson và đánh giá full-scene Việt Nam còn cần thực hiện.

## Kiểm tra

```powershell
python -m pytest tests -q
node --test tests/frontend_auth.test.cjs tests/frontend_routing.test.cjs tests/frontend_management.test.cjs tests/frontend_reports.test.cjs
python scripts/test_end_to_end_flow.py

# Opt-in: checkpoint thật, CPU và database/kho ảnh tạm.
# Test ảnh có biển cần archive/Test/11052.png; không tải dataset/weights.
$env:SIGNSIGHT_TEST_REAL_YOLO = '1'
.\.venv-yolo\Scripts\python.exe -m pytest tests/test_yolo_checkpoint_integration.py -q
Remove-Item Env:\SIGNSIGHT_TEST_REAL_YOLO
```

Tests bao gồm ACL, upload tĩnh/metadata/orientation/size/chunked request, integrity hash, thiếu model, bbox/class sai, 0/nhiều detections, class correction, batch rollback, lỗi evidence, cạnh tranh review, 30 ngày, chống data leakage và provenance train/eval. Test CNN thật được bỏ qua nếu checkout không có checkpoint. Browser chưa có kết nối trong session này nên chưa kiểm tra tương tác web trực tiếp.

Lần tích hợp 07/10/2026: **126 tests Python pass** với real-YOLO checks bật, **14 tests JavaScript pass**, integration script pass trên DB tạm. Test thật xác minh upload → detect → gửi → manager duyệt → map/evidence, và ảnh trắng trả run rỗng ở ngưỡng mới. Xem báo cáo integration (tài liệu nội bộ, không kèm bản public); chưa nghiệm thu UI điện thoại hay detection full-scene.

Tham khảo kỹ thuật: [Ultralytics detection datasets](https://docs.ultralytics.com/datasets/detect/), [predict](https://docs.ultralytics.com/modes/predict/), [train](https://docs.ultralytics.com/modes/train/), [validation metrics](https://docs.ultralytics.com/modes/val/), [YOLO11](https://docs.ultralytics.com/models/yolo11/), [Pillow Image verification](https://pillow.readthedocs.io/en/stable/reference/Image.html).
