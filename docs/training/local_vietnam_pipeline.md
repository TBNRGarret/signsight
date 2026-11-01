# Pipeline dataset Việt Nam trên máy local

Từ thư mục gốc dự án: **EDA → duyệt nhãn/split → chuẩn hóa YOLO → kiểm tra → train → test cuối cùng**. Script: `scripts/local_detection_pipeline.py`. Dùng môi trường `.venv-yolo` hiện có, không cần chạy backend/frontend.

Máy hiện tại đã kiểm tra: PyTorch 2.6.0+cu124, RTX 3060 Laptop **6 GB VRAM**. Cấu hình khởi đầu là **YOLO11s, imgsz 640, batch 2, workers 0**. Đây là điểm bắt đầu để đo bộ nhớ/thời gian, chưa phải kết quả benchmark trên hai dataset mới. Hết VRAM: giảm batch xuống 1, hoặc dùng YOLO11n. Chỉ thử YOLO11m sau khi đo cấu hình nhỏ.

## 1. Đặt dữ liệu vào máy

```text
data/vietnam_raw/
  vitsdb/       # ZIP tải về HOẶC các file đã giải nén
  supsign/      # ZIP tải về HOẶC các file đã giải nén
```

Không để cả ZIP và bản giải nén của cùng dataset dưới một source, vì sẽ đếm ảnh hai lần. Có thể thay bằng thư mục ngoài project; giữ tên source nhất quán giữa các lần chạy. Chạy một bộ trước bằng cách chỉ truyền một `--source`.

**Local không giải quyết quyền Kaggle 403.** Tải bằng tài khoản có quyền hoặc nhận file trực tiếp từ thầy. API token xác thực tài khoản, không tự cấp quyền xem dataset riêng ([KaggleHub](https://github.com/Kaggle/kagglehub)). Pipeline dưới đây đọc file local, không gọi Kaggle.

ZIP được đọc trực tiếp khi EDA. Khi prepare, ảnh và nhãn YOLO được chép sang dataset mới; cần dung lượng cho cả nguồn lẫn bản chuẩn hóa. Nguồn ZIP khoảng 30 GB không có nghĩa bản chuẩn hóa cũng chỉ 30 GB; kiểm tra dung lượng giải nén thực tế. Không ghi đè nguồn hoặc output đã tồn tại.

## 2. EDA toàn bộ ảnh/nhãn

Trong PowerShell tại thư mục dự án:

```powershell
$py = '.\.venv-yolo\Scripts\python.exe'
& $py -m scripts.local_detection_pipeline eda --source 'vitsdb=data/vietnam_raw/vitsdb' --source 'supsign=data/vietnam_raw/supsign' --output .cache/vietnam_eda_v1
```

Đọc và giải mã **toàn bộ** ảnh, hash SHA-256 toàn bộ, không phải sample. Có log mỗi 1.000 ảnh. Nguồn lớn sẽ mất thời gian đọc ổ đĩa; chưa dùng GPU.

Nếu dataset có cả YOLO và COCO cho cùng ảnh, thêm `--annotation-format yolo` hoặc `--annotation-format coco` vào lệnh EDA. Mặc định auto giữ cảnh báo ambiguous; không tự trộn hai bản annotation. Lựa chọn được lưu vào plan và dùng lại khi prepare.

Output:

- `audit.json`: tổng ảnh, box, class map, nhãn thiếu/rỗng/sai, lỗi từng file, bbox đã chuẩn hóa, hash ảnh.
- `duplicate_groups.json`: ảnh trùng byte trong/cross dataset và split; chưa phát hiện frame gần giống hoặc ảnh nén lại.
- `plan.json`: nguồn, thứ tự lớp đích và mapping từng `(dataset, namespace, class_id)`.
- `assignments.csv`: mỗi ảnh có `dataset,path,split,group,exclude_reason`.

Hỗ trợ YOLO detection TXT 5 cột, Pascal VOC XML, COCO JSON. CSV/custom, segmentation, archive lồng/RAR/7z cần adapter riêng. Chưa có file thật của hai bộ để xác nhận format/class count. Với VOC, bbox được diễn giải theo tọa độ liên tục `xmax-xmin`; kiểm tra quy ước của bộ nguồn nếu dùng pixel endpoint inclusive. COCO crowd sẽ bị chặn khi prepare.

## 3. Duyệt cấu hình dữ liệu

Mở `.cache/vietnam_eda_v1/plan.json`:

- `names`: thứ tự lớp YOLO mới. Có thể giữ tất cả lớp thực tế của bộ dữ liệu, không bị ép còn 10 lớp cũ.
- `class_map[*].target`: tên trong `names`. Tên lấy từ nguồn chỉ là đề xuất; không coi class ID hai bộ là tương đương. `null` nghĩa cần điền mapping.
- Sau khi đối chiếu nhãn mẫu và taxonomy, đặt `reviewed: true`.
- Kiểm tra nguồn gốc train/val/test độc lập; sau khi kiểm tra đặt `split_reviewed: true`.
- Nếu thực sự đã xác nhận ảnh có annotation rỗng là ảnh âm tính hợp lệ, đặt `empty_annotations_reviewed: true`. Thiếu file nhãn không được tự biến thành negative.

Không bỏ object ngoài taxonomy bằng cách xóa dòng nhãn. Hãy mở rộng taxonomy hoặc loại **cả ảnh** có lý do trong `exclude_reason`. Thao tác này không xóa ảnh nguồn. Mọi ảnh còn lại phải có nhãn hợp lệ và mapping đầy đủ.

Mặc định giữ split từ tên thư mục `train/val/test`. Với ảnh có `split=unknown`, cần gán split có cơ sở, ưu tiên theo nhóm phiên quay/địa điểm/biển vật lý. Điền `group` nhất quán giữa hai bộ nếu chúng dùng chung cùng phiên/biển.

Nếu cần chia lại toàn bộ, **điền group cho mọi ảnh được giữ lại trước**, rồi chạy:

```powershell
& $py -m scripts.local_detection_pipeline split --assignments .cache/vietnam_eda_v1/assignments.csv --output .cache/vietnam_eda_v1/assignments_grouped.csv
```

Lệnh này thay các split của ảnh được giữ lại bằng chia khoảng **70/15/15 theo số nhóm**, seed 42; không cân bằng theo số ảnh/lớp. Cần ít nhất 3 nhóm. Sửa `assignments` trong plan thành `assignments_grouped.csv`, kiểm tra phân bố lớp và split lần nữa. Không chia ngẫu nhiên từng frame. Nhóm để trống khi giữ split gốc được ghi rõ là chưa có metadata nhóm; không phải bằng chứng không rò rỉ.

## 4. Chuẩn hóa và kiểm tra

```powershell
& $py -m scripts.local_detection_pipeline prepare --plan .cache/vietnam_eda_v1/plan.json --output data/vietnam_yolo/v1
& $py -m scripts.local_detection_pipeline validate --data data/vietnam_yolo/v1/data.yaml
```

Prepare đọc lại nhãn và hash nguồn, chuyển bbox sang YOLO, chép ảnh, viết `data.yaml` và `manifest.json`. Chặn nhãn thiếu/sai, class chưa map, COCO crowd, ảnh trùng byte giữa split và group xuất hiện ở nhiều split. Output chỉ xuất hiện khi prepare thành công. Mọi split phải có ảnh và mọi lớp đích phải có annotation trong train. Thiếu lớp ở validation/test được ghi vào `missing_classes`, không tự thêm ảnh hoặc bịa chỉ số cho lớp đó.

```text
data/vietnam_yolo/v1/
  data.yaml
  manifest.json
  images/{train,val,test}/
  labels/{train,val,test}/
```

Trước mỗi train/evaluate, script kiểm tra lại manifest, ảnh, nhãn, checksum và split. Không sửa tay bản đã chuẩn hóa; sửa nguồn/plan rồi xuất `v2`. Sau khi đổi tập train, xóa cache Ultralytics chỉ ở phiên bản bỏ đi hoặc prepare phiên bản mới. Không di chuyển bản chuẩn hóa mà giữ `path` cũ trong YAML.

## 5. Train thử 1 epoch, sau đó train đầy đủ

```powershell
& $py -m scripts.local_detection_pipeline train --data data/vietnam_yolo/v1/data.yaml --model yolo11s.pt --allow-download --epochs 1 --batch 2 --imgsz 640 --device 0 --output runs/vietnam_smoke_v1
```

`--allow-download` cho phép tải trọng số YOLO11 chính thức nếu chưa có local. Muốn tránh tải, truyền đường dẫn checkpoint đã có và bỏ cờ này. Cấu hình tắt flip ngang/dọc vì có biển chỉ hướng; `amp=False`, không cache toàn bộ ảnh trong RAM, workers 0 cho Windows. Cần đo VRAM ở chính dataset của bạn.

Sau khi smoke chạy ổn và kiểm tra ảnh batch/nhãn, bắt đầu một run mới từ pretrained weights:

```powershell
& $py -m scripts.local_detection_pipeline train --data data/vietnam_yolo/v1/data.yaml --model yolo11s.pt --allow-download --epochs 50 --batch 2 --imgsz 640 --device 0 --output runs/vietnam_yolo11s_v1
```

Train chỉ dùng train/val; chưa chạy test giữ riêng. Chọn epoch/model/imgsz bằng validation. Theo dõi loss, precision/recall, mAP50 và mAP50-95, confusion matrix và ảnh dự đoán. Các thiết lập theo [tài liệu train của Ultralytics](https://docs.ultralytics.com/modes/train/).

Nếu bị ngắt giữa quá trình, Ultralytics hỗ trợ resume `last.pt` gồm optimizer và epoch. Sau khi kiểm tra lại dataset, có thể dùng CLI trong cùng môi trường:

```powershell
& $py -m scripts.local_detection_pipeline validate --data data/vietnam_yolo/v1/data.yaml
.\.venv-yolo\Scripts\yolo.exe detect train resume=True model=runs/vietnam_yolo11s_v1/weights/last.pt
```

Lệnh resume native không đi qua wrapper ghi `pipeline_report.json`; thông tin run vẫn nằm trong `args.yaml`/`results.csv`. Truyền `--model last.pt` vào lệnh train của wrapper là bắt đầu lượt fine-tune mới, không phải resume optimizer.

## 6. Đánh giá test sau khi chốt cấu hình

```powershell
& $py -m scripts.local_detection_pipeline evaluate --data data/vietnam_yolo/v1/data.yaml --model runs/vietnam_yolo11s_v1/weights/best.pt --batch 2 --imgsz 640 --device 0 --split test --output runs/vietnam_test_v1
```

Giữ `weights/best.pt`, `weights/last.pt`, `results.csv`, `args.yaml`, các plots và `pipeline_report.json` cùng `data.yaml`/`manifest.json`. Report ghi checksum checkpoint/manifest và metrics đánh giá. Chưa dùng test để tune.

Checkpoint mới là thí nghiệm với taxonomy đã chọn. Backend hiện yêu cầu đúng 10 tên lớp và đúng thứ tự SignSight; model nhiều lớp cần cập nhật mapping/detector và kiểm thử tích hợp trước khi thay model đang phục vụ. Pipeline không tự kích hoạt model trong API.

## Kiểm thử

```powershell
& $py -m pytest tests/test_local_detection_pipeline.py tests/test_dataset_eda.py -q
```

Đã chạy 25 test gồm EDA và pipeline; fixture nhỏ và mock YOLO kiểm tra orchestration. Cũng đã chạy thông EDA → prepare → train 1 epoch → evaluate bằng YOLO11n thật trên CUDA, dùng 3 ảnh giả lập 64×64, lưu riêng ở `.cache/local-pipeline-_348kfpt`. Ultralytics có cảnh báo vẽ labels do fixture chỉ có một box train; train/evaluate và các report vẫn hoàn tất. Đây chỉ là kiểm tra luồng chạy, không phải benchmark YOLO11s/640 hoặc kết luận chất lượng hai dataset thật. Chưa khởi chạy một lượt train lớn.
