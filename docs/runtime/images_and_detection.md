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

Web user thử đóng góp: http://127.0.0.1:8000/web/observations.html. Chọn/chụp ảnh để tự upload và nhận diện; kiểm tra nhãn, xác nhận vị trí từng biển rồi gửi. Manager/admin vào http://127.0.0.1:8000/web/management.html để duyệt; staff tự chuyển về đây sau đăng nhập. Biển được chấp nhận xuất hiện trên bản đồ. App Flutter chưa triển khai. Xem [web quản trị](web_and_management.md) và [dữ liệu local](../getting-started/local_development.md).

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
| `POST /api/v1/images/{id}/classify` | Retired; HTTP 410 after authentication. Historical classification runs remain readable. |
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

The GTSRB converters and baseline evaluator are retained under `training/legacy_baseline/`, with compatibility CLI imports under `ai_engine/`. They support old experiments and do not train a Vietnam production detector.

For new work use the [two SupSign notebooks](../training/supsign_yolo11s_colab.md), then [reviewed model activation](model_activation.md). The retired CNN classify routes return HTTP 410 after authentication; historical CNN runs remain readable. New predictions use YOLO only. No missing checkpoint is replaced with heuristic predictions.
