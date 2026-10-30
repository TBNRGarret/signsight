# SupSign → YOLO11s trên Colab

Notebook: [SignSight_SupSign_YOLO11s_Colab.ipynb](../notebooks/SignSight_SupSign_YOLO11s_Colab.ipynb).

1. Upload notebook `.ipynb` lên Colab và lưu bản riêng của bạn. Dán **link file ZIP SupSign 107 lớp** hoặc file ID vào `SOURCE_URL`; file cần cho phép tải qua link, không dùng link folder. `gdown` tải về thư mục local `WORK/downloads/DATASET_VERSION/`, không cần dataset nằm trong My Drive của tài khoản Colab mới. Không có link dataset cá nhân được nhúng sẵn trong notebook public.
2. Mở notebook bằng Colab, chọn GPU runtime, mount Drive rồi chạy đến EDA và xem ảnh/bbox trước. Sau khi kiểm tra nhãn, đổi `LABEL_REVIEWED=True` rồi chạy cell train. Mặc định **YOLO11s pretrained, 35 lớp, 80 epochs, imgsz 640, batch 8**. Hết VRAM thì dùng run mới với batch 4. `SMOKE=True` chỉ chạy 1 epoch để thử luồng.
3. `SAVE_TO_DRIVE=True` mặc định mount Drive của **tài khoản hiện tại** để giữ cache/checkpoint/EDA. `False` không mount Drive và ghi vào `/content/signsight_supsign/outputs`; phải tải kết quả trước khi mất runtime. **Lưu notebook không lưu dataset hoặc weights.** Runtime mới có cache thì khôi phục, không xử lý ZIP gốc lại. Đổi `DATASET_VERSION` khi thay nguồn/code/lớp/grouping; cache không tự đoán nội dung ZIP nguồn đã thay.
4. Run mới dùng `RUN_NAME` mới. Khi runtime ngắt, giữ tên/cấu hình và đặt `RESUME=True` để dùng `last.pt`. Resume kiểm tra fingerprint dataset và cấu hình. Run đã hoàn tất có thể không resume được do optimizer đã được strip.
5. Chọn model/settings theo validation. Test chỉ chạy khi bật `RUN_HELDOUT_TEST=True`; metrics ghi rõ loại split. Cell ảnh riêng nhận upload ảnh đường phố để xem bbox.
6. Cell cuối tải ZIP bằng `google.colab.files.download`, đồng thời lưu tại `PERSIST/exports/` (Drive hoặc local). ZIP kết quả chứa weights, plots, metrics, cấu hình và manifest, không chứa toàn bộ dataset.

## Đổi tài khoản Colab

- Dataset gốc: giữ nguyên `SOURCE_URL` để tải từ cùng file chia sẻ. Helper không dùng cookies/đăng nhập của tài khoản cũ. Quyền truy cập và quota tải Drive vẫn áp dụng; xem [gdown 5.2](https://github.com/wkentaro/gdown/tree/v5.2.0).
- Tránh audit lại: ở tài khoản cũ đã chuẩn bị thành công, chia sẻ file `datasets/DATASET_VERSION.zip` và lấy SHA-256 trong file `.zip.sha256`. Điền `PREPARED_CACHE_URL` và `PREPARED_CACHE_SHA256` ở tài khoản mới. Notebook tải cache bằng gdown, kiểm tra SHA-256/recipe/hash ảnh-nhãn rồi khôi phục. Hai trường này có thể để trống khi chạy lần đầu.
- Checkpoint không tự chuyển tài khoản: nếu resume, mang theo toàn bộ thư mục run gồm `weights/last.pt`, `training_request.json` và cấu hình sang `PERSIST/runs/RUN_NAME` của tài khoản mới; giữ đúng dataset và settings. Chỉ tải `best.pt` về không đủ để resume run.
- `SOURCE_SHA256` tùy chọn xác nhận đúng ZIP gốc. Một ZIP local đã có từ phiên bản cũ mà chưa có receipt nguồn chỉ được nhận lại khi SHA-256 khớp; helper không tự ghi đè file chưa xác định nguồn. Tải gián đoạn có thể chạy lại cell trong cùng runtime để tiếp tục phần tải của gdown.
- Notebook đã chứa helper tải và chuẩn bị dữ liệu. Upload bản `.ipynb` là đủ, không phải clone repo. Lưu bản cấu hình có link riêng trên Drive của bạn; giữ link dataset/checkpoint và credentials ra khỏi GitHub public.

EDA chạy trên dataset đã chuẩn hóa: số ảnh/box và lớp theo split, negative, kích thước ảnh/box, box nhỏ dưới 16 px sau resize, nhóm trùng/cách ly và lớp thiếu. Kết quả lưu trên Drive trong `eda/DATASET_VERSION/`: `dataset_eda.json`, `class_counts.csv`, `images.csv`, `boxes.csv`, `eda_overview.png`; đồng thời được đóng gói vào ZIP kết quả. Preview bbox giúp rà soát nhưng không chứng minh toàn bộ nhãn đúng.

Bản sửa chia nhóm dùng mặc định `DATASET_VERSION=supsign107-car35-v3`, run `yolo11s_car35_640_v3`; giữ nguyên cache/run cũ để tránh trộn recipe hoặc resume khác cấu hình. Notebook kiểm tra fingerprint, không ghi đè run cũ để tiếp tục tùy tiện.

## Nếu gặp `Missing train classes after grouping`

V2 có thể đặt toàn bộ nhóm chứa một lớp hiếm vào val/test. V3 giữ đủ lớp train trước khi cân bằng tỷ lệ, giữ nguyên nhóm và không nhân bản ảnh qua split. Nếu chỉ có một nhóm cho lớp đó, val/test sẽ thiếu lớp và báo rõ; không được kết luận chất lượng lớp đó bằng mAP tổng. Nếu không tồn tại ba split không rỗng mà vẫn đủ lớp train, pipeline dừng với thông báo ràng buộc nhóm không khả thi.

Nếu runtime cũ còn giữ traceback của lỗi, chạy cell này **ngay dưới cell lỗi**, trước khi restart hoặc chạy lại cell nhúng pipeline cũ:

```python
import sys
from urllib.request import urlopen
_SIGNSIGHT_PREP_TRACEBACK = getattr(sys, 'last_traceback', None) or getattr(getattr(sys, 'last_exc', None), '__traceback__', None)
exec(urlopen('https://raw.githubusercontent.com/TBNRGarret/signsight/main/scripts/recover_supsign_colab.py', timeout=30).read().decode('utf-8'))
```

Cell tải helper đã sửa, lấy lại các hàng đã audit và gom nhóm từ traceback trong RAM, kiểm tra inventory ZIP, chia lại rồi ghi dataset/cache. Không chạy lại audit/dHash; vẫn phải đọc/ghi ảnh và lưu cache nên chưa hoàn tất ngay. ZIP nguồn được giữ nguyên. Sau `Recovery complete`, tiếp tục EDA, xem lại nhãn rồi train. Biến `RECIPE` và các helper trong notebook được cập nhật để các cell sau dùng đúng bản sửa; tên/path của run đang mở được giữ lại.

Nếu traceback đã mất hoặc runtime đã restart, mở lại notebook V3 và chạy từ đầu. Có thể cần chuẩn bị lại dữ liệu vì lần bị lỗi trước đó chưa ghi cache hoàn chỉnh; không cần upload lại ZIP đã nằm trên Drive. Cell phục hồi là tùy chọn khi gặp lỗi, không phải bước chạy trong luồng bình thường.

## Chuẩn hóa và giới hạn đánh giá

Pipeline tự đọc toàn bộ YOLO annotation, xác minh ảnh và hash SHA-256. Lọc lớp theo **tên**, tạo ID 0–34 theo `CAR35`; không dùng nguyên ID của bộ nguồn. Nhãn lỗi/mất nhãn và nhóm trùng byte nhưng khác annotation được cách ly cả ảnh, ghi lý do trong manifest. Không sửa ZIP nguồn. Ảnh hợp lệ chỉ chứa lớp ngoài scope được giữ làm negative cho taxonomy đích.

Bỏ split nguồn. Ảnh trùng byte chỉ giữ một bản; các alias vẫn được dùng để nối nhóm. Không có nhóm do người thu thập cung cấp thì dùng block tên ảnh/frame và dHash BK-tree để gom các ảnh có khả năng liên quan. Đây là heuristic, có thể gộp nhầm hoặc bỏ sót ảnh gần giống. Không được coi đó là bằng chứng test độc lập. Nếu nhóm quá ít hoặc không thể đưa đủ lớp vào train, notebook dừng thay vì tự phá nhóm để đạt số lượng.

Tùy chọn `GROUPS_CSV` có cột `path,group`, ví dụ:

```csv
path,group
train/images/33292.png,trip_01
test/images/33292.png,trip_01
```

CSV phải bao phủ mọi ảnh hợp lệ còn dùng, kể cả alias ảnh trùng. Nhóm ghi theo phiên quay/địa điểm/biển vật lý thật; dHash vẫn được dùng bổ sung để nối các nhóm có ảnh gần giống. Ngay khi có CSV, tập test của dataset vẫn không tự biến thành tập thực địa mới. Cần bộ thu thập qua kính ô tô độc lập để đánh giá sản phẩm.

Manifest lưu provenance, hash ảnh/nhãn, bản sao bị loại, lý do cách ly, grouping recipe, class counts và lớp thiếu theo split. Lớp thiếu val/test được hiển thị; không suy diễn điểm số của chúng từ mAP tổng. Dữ liệu ít mẫu như cấm vượt cần được thu thập thêm, không nhân bản ảnh sang val/test.

## Tích hợp hệ thống

Model mới có 35 tên lớp dataset, chưa phải QCVN mapping đã nghiệm thu. Backend hiện yêu cầu taxonomy 10 lớp: **không chép weights mới vào đường dẫn checkpoint phục vụ app**. Cần mở rộng catalog/mapping/validation và giữ ý nghĩa ID các record cũ bằng migration có test trước khi tích hợp.

Sau khi tải ZIP, chạy từ repo root để kiểm tra ứng viên (đường dẫn report lấy từ thư mục export):

```powershell
python -m scripts.inspect_yolo_candidate --checkpoint 'PATH_TO_BEST_PT' --evaluation 'PATH_TO_VALIDATION_JSON' --output '.cache/candidate-review.json' --verify-model
```

Công cụ xác minh hash checkpoint, tên/thứ tự class, metrics validation từng lớp, thiếu ground truth và tương thích runtime. Ngưỡng mặc định precision 0,85/recall 0,80 từng lớp chỉ là mục tiêu rà soát của dự án, không bảo đảm an toàn. Report tự khai có field test vẫn cần xem bằng chứng; công cụ không tự thay weights. Với model 35 lớp, runtime hiện tại sẽ báo chặn taxonomy như dự kiến.

Notebook được tạo từ `scripts/generate_supsign_notebook.py`, nhúng hai module đã kiểm thử. Chạy lại generator sau khi sửa helper:

```bash
python -m scripts.generate_supsign_notebook
python -m pytest tests/test_supsign_training.py -q
```

API YOLO11/train/resume theo [tài liệu Ultralytics](https://docs.ultralytics.com/modes/train/). Máy GPU được cấp thực tế quyết định batch và thời gian train; chưa có benchmark SupSign/35 lớp từ notebook này.
