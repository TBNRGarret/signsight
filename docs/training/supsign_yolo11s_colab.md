# SupSign → YOLO11s trên Colab

## Luồng hai notebook: EDA trước, train sau

1. Upload [SignSight_SupSign_EDA_Colab.ipynb](../../notebooks/SignSight_SupSign_EDA_Colab.ipynb) lên Colab, dùng **CPU runtime**. Điền `SOURCE_URL` bằng link file ZIP SupSign cho phép tải qua link. Giữ `SAVE_TO_DRIVE=True` để lưu dataset cache qua các phiên.
2. Chạy hết notebook EDA. Cell cuối tải `DATASET_VERSION_eda_TIMESTAMP.zip`: **gửi ZIP báo cáo này để rà soát trước**, không cần gửi cache dataset lớn. Báo cáo chứa thống kê subset CAR35, audit tổng quan nguồn, CSV, biểu đồ, ảnh bbox preview, manifest và `training_handoff.json`. Đây chưa phải đánh giá model.
3. Giữ `datasets/DATASET_VERSION.zip` và `.zip.sha256` trên Drive. Cache chứa dataset đã lọc/chia nhóm; ZIP báo cáo chỉ chứa báo cáo và ảnh preview.
4. Sau khi rà soát, upload [SignSight_SupSign_YOLO11s_Train_Colab.ipynb](../../notebooks/SignSight_SupSign_YOLO11s_Train_Colab.ipynb), chọn **GPU**. Cùng tài khoản: giữ nguyên `DATASET_VERSION` và thư mục Drive. Khác tài khoản: chia sẻ cache ZIP rồi điền `PREPARED_CACHE_URL`, `PREPARED_CACHE_SHA256` từ `cache_sha256` trong handoff. Điền `EXPECTED_MANIFEST_SHA256` từ `manifest_sha256` để đối chiếu đúng dataset đã xem.
5. Train chỉ khôi phục và xác minh cache, không audit ZIP thô/chia split lại. Không cần nhập lại CSV nhóm. Bật `LABEL_REVIEWED=True` sau khi kiểm tra nhãn. Nếu thay lớp/grouping/code chuẩn bị, quay lại EDA và tạo cache phiên bản mới.
6. Train mặc định YOLO11s pretrained, 80 epochs, 640 px, batch 8; validation trước, held-out test chỉ chạy khi bật riêng. Cell cuối tải ZIP weights/metrics/config/manifest, không kèm toàn bộ dataset.

EDA chạy được bằng CPU nhưng lần đầu vẫn phải tải, decode/hash và gom nhóm toàn bộ nguồn; không có thời gian chạy cố định. Notebook không cần clone repo hoặc Kaggle key. Khi `SAVE_TO_DRIVE=False`, cache và báo cáo chỉ ở runtime; phải tải cache ZIP **cùng checksum** trước khi runtime mất nếu muốn train sau.

Hai notebook dùng nguyên code chuẩn bị/cache đã kiểm thử, không đổi recipe hiện tại. Có thể tái sử dụng cache V3 hợp lệ. Bản gộp cũ vẫn được giữ để tương thích các phiên đang mở.

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

Notebook được tạo từ `scripts/generate_supsign_notebook.py`, nhúng ba module đã kiểm thử (EDA, training và gdown). Chạy lại generator sau khi sửa helper:

```bash
python -m scripts.generate_supsign_notebook
python -m pytest tests/test_supsign_training.py -q
```

API YOLO11/train/resume theo [tài liệu Ultralytics](https://docs.ultralytics.com/modes/train/). Máy GPU được cấp thực tế quyết định batch và thời gian train; chưa có benchmark SupSign/35 lớp từ notebook này.
