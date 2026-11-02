# SupSign → YOLO11s trên Colab

## Luồng hai notebook: EDA trước, train sau

1. Upload [SignSight_SupSign_EDA_Colab.ipynb](../../notebooks/SignSight_SupSign_EDA_Colab.ipynb) lên Colab, dùng **CPU runtime**. Chỉ tải dataset bằng **gdown**, không mount Drive hoặc ghi vào tài khoản. Nếu đã có cache, điền `PREPARED_CACHE_URL` và checksum; nếu chưa có, điền `SOURCE_URL` bằng link ZIP SupSign gốc.
2. Chạy hết notebook EDA. Cell cuối tải `DATASET_VERSION_eda_TIMESTAMP.zip`: **gửi ZIP báo cáo này để rà soát trước**, không cần gửi cache dataset lớn. Báo cáo chứa thống kê subset CAR35, audit tổng quan nguồn, CSV, biểu đồ, ảnh bbox preview, manifest và `training_handoff.json`. Đây chưa phải đánh giá model.
3. Mặc định `DOWNLOAD_PREPARED_CACHE=True` tải thêm cache ZIP lớn và `.zip.sha256` về máy, có thể cần cho phép nhiều lượt tải. Cache chứa dataset đã lọc/chia nhóm; ZIP báo cáo nhỏ không dùng để train. Nếu cache cũ đã được lưu an toàn, đặt False để chỉ tải báo cáo.
4. Sau khi rà soát, upload [SignSight_SupSign_YOLO11s_Train_Colab.ipynb](../../notebooks/SignSight_SupSign_YOLO11s_Train_Colab.ipynb), chọn **GPU**. Runtime/tài khoản mới: tự lưu/chia sẻ cache thành file cho phép tải qua link, điền `PREPARED_CACHE_URL`, `PREPARED_CACHE_SHA256` từ handoff; notebook tải bằng gdown. Điền `EXPECTED_MANIFEST_SHA256` để khóa đúng dataset đã xem. Không có bước tự upload hoặc mount.
5. Train chỉ khôi phục và xác minh cache, không audit ZIP thô/chia split lại. Không cần nhập lại CSV nhóm. Bật `LABEL_REVIEWED=True` sau khi kiểm tra nhãn. Nếu thay lớp/grouping/code chuẩn bị, quay lại EDA và tạo cache phiên bản mới.
6. Train mặc định YOLO11s pretrained, 80 epochs, 640 px, batch 8; validation trước, held-out test chỉ chạy khi bật riêng. Cell cuối tải ZIP weights/metrics/config/manifest, không kèm toàn bộ dataset.

EDA chạy được bằng CPU nhưng lần đầu vẫn phải tải, decode/hash và gom nhóm toàn bộ nguồn; không có thời gian chạy cố định. Notebook không cần clone repo, Kaggle key hoặc đăng nhập Drive. Mọi file nằm dưới `/content/signsight_supsign`, sẽ mất khi runtime bị xóa. Tải kết quả/cache cần giữ trước khi ngắt. `RESUME=True` chỉ dùng khi RUN_DIR còn `last.pt` và `training_request.json` đúng settings; notebook chưa tự khôi phục backup run ở runtime mới.

Hai notebook dùng nguyên code chuẩn bị/cache đã kiểm thử, không đổi recipe hiện tại. Có thể tái sử dụng cache V3 hợp lệ. Bản gộp cũ nằm trong Git history; dùng hai notebook tách biệt cho phiên mới.

## Task 1: rà grouping trên CPU

Upload lại notebook EDA mới để có cell **Rà nhóm trước khi quyết định train lại**. Giữ `DATASET_VERSION='supsign107-car35-v3'`, điền `PREPARED_CACHE_URL` bằng link cache ZIP đã lưu và `PREPARED_CACHE_SHA256` bằng checksum tương ứng. Notebook dùng gdown tải cache vào /content, không audit lại ZIP thô. Đặt `DOWNLOAD_PREPARED_CACHE=False` nếu chỉ muốn tải báo cáo mới và cache cũ đã được giữ an toàn. Nếu chưa có cache, dùng `SOURCE_URL` để chuẩn bị từ ZIP gốc.

Sau khi chạy hết và tải ZIP báo cáo, giải nén rồi mở `grouping/index.html`. Nếu chạy lại cell grouping, notebook giữ bản trước và in tên thư mục `grouping_TIMESTAMP` mới. Đọc theo thứ tự:

1. **Review flags / Splits:** số nhóm, số ảnh, tỷ lệ ảnh thuộc nhóm lớn nhất của từng split. Ít hơn 5 nhóm hoặc một nhóm chiếm trên 50% ảnh là cờ cần xem lại, không phải kết luận rò rỉ dữ liệu.
2. **Global dHash review:** tối đa 12 cặp, chia tối đa 3 trang ảnh, chọn từ toàn bộ nhóm chứ không chỉ top 12. Ưu tiên phủ khoảng cách hash và nhiều nhóm; `dhash_edges.csv` chứa mọi cạnh dHash trong forest tái dựng. Đây chưa phải mọi cặp near-duplicate và không tự xác nhận cạnh nối đúng/sai.
3. **Ảnh nhóm và cặp liên kết:** ảnh mẫu của tối đa 12 nhóm lớn nhất, bbox/nhãn và tối đa 3 cặp nối nhóm mỗi nhóm. Mỗi loại liên kết có suất trước khi thêm ví dụ collision, để filename không lấn hết dHash. Ảnh mẫu trải theo tên nguồn, không đảm bảo bao quát mọi nội dung trong nhóm.
4. **Class coverage:** số box, ảnh và nhóm chứa từng lớp theo train/val/test. Số 0 ở holdout nghĩa là chưa đánh giá được lớp đó.
5. **CSV đầy đủ:** `groups.csv`, `group_members.csv` (đường dẫn nguồn và alias), `grouping_edges.csv`, `dhash_edges.csv` và `class_coverage.csv`. JSON lưu checksum manifest/content identity và mức khớp của replay.

`partition_matches=True` chỉ xác nhận phân hoạch tái dựng khớp manifest. Báo cáo lưu một spanning forest đủ nối nhóm, không xuất mọi cặp tương tự và không giả làm log lịch sử. Capture-group cache cần đúng CSV gốc khi khôi phục EDA theo recipe; API báo cáo riêng có thể đọc cache thiếu CSV nhưng sẽ ghi `evidence_complete=False`, không suy ra capture bằng tên file.

Decode dHash vẫn đọc ảnh cache trên CPU và có thanh tiến độ; không cần GPU. Báo cáo được ghi bên ngoài dataset, giữ nguyên ảnh/nhãn/manifest/split. **Gửi ZIP báo cáo này để rà trước khi quyết định sửa grouping, tạo dataset phiên bản mới hoặc train tiếp.**

## Source and compatibility

Only the EDA and training notebooks above are supported. Generic readers, local training CLI and baseline tools are retained. The five historical notebook variants and their generators were retired; Git history preserves them.

The training notebook accepts known V1 preparation signatures and verifies archive/image/label hashes without rewriting the old manifest. New datasets use recipe V2. Unsupported recipes stop explicitly. Keep `EXPECTED_MANIFEST_SHA256` when you want to bind the exact reviewed artifact; runtime paths do not affect the separate content fingerprint. Raw file checksums are never replaced by the content fingerprint.

## Tích hợp hệ thống

Model mới có 35 tên lớp dataset, chưa phải QCVN mapping đã nghiệm thu. Backend đã hỗ trợ catalog mở rộng và mapping riêng theo checkpoint, giữ nguyên ID cũ; **không chép weights mới đè lên model đang phục vụ**. Làm theo [hướng dẫn mapping, kiểm tra và tích hợp trên bản sao runtime](../runtime/model_activation.md).

Sau khi tải ZIP, chạy từ repo root để kiểm tra ứng viên (đường dẫn report lấy từ thư mục export):

```powershell
python -m scripts.inspect_yolo_candidate --checkpoint 'PATH_TO_BEST_PT' --evaluation 'PATH_TO_VALIDATION_JSON' --output '.cache/candidate-review.json' --verify-model
```

Công cụ xác minh hash checkpoint, tên/thứ tự class, metrics validation từng lớp, thiếu ground truth và tương thích runtime. Với model mới, thêm `--catalog` và `--mapping` đã rà như hướng dẫn trên; không cung cấp mapping thì chỉ kiểm tra tương thích taxonomy cũ. Ngưỡng mặc định precision 0,85/recall 0,80 từng lớp là mục tiêu rà soát của dự án. Report tự khai có field test vẫn cần xem bằng chứng; công cụ không tự thay weights.

Notebook được tạo từ `scripts/generate_supsign_notebook.py`, nhúng các module đã kiểm thử trong `training/` cùng compatibility entry points. Chạy lại generator sau khi sửa helper:

```bash
python -m scripts.generate_supsign_notebook
python -m pytest tests/test_supsign_training.py -q
```

API YOLO11/train/resume theo [tài liệu Ultralytics](https://docs.ultralytics.com/modes/train/). Máy GPU được cấp thực tế quyết định batch và thời gian train; chưa có benchmark SupSign/35 lớp từ notebook này.
