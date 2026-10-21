# Giao thức dataset thực địa (pilot)

Cập nhật 10/10/2026. Checkpoint YOLO hiện tại chỉ được đánh giá trên ảnh GTSRB đã cắt quanh biển. Pilot này tạo một tập ảnh đường phố Việt Nam nhỏ nhưng độc lập, dùng để đo baseline của checkpoint đó, chọn lại ngưỡng confidence và làm tập đánh giá cố định cho các lần train sau. Chưa có ảnh nào được chụp; phần này cần nhóm ra đường.

Không cần công cụ mới: gán nhãn bằng công cụ có sẵn, rồi dùng `validate`/`evaluate` của `ai_engine.train_detection`.

## Mục tiêu và cỡ mẫu

- 20–30 ảnh toàn cảnh cho mỗi lớp trong 10 lớp, chụp ở TP.HCM, cộng khoảng 40 ảnh không có biển trong taxonomy.
- Ảnh âm tính nên gồm đường phố không có biển, biển Việt Nam ngoài taxonomy (cấm đỗ, cấm rẽ, chỉ dẫn...), bảng quảng cáo đỏ/tròn và đèn giao thông. Đây là nguồn đo false positive.
- Mỗi biển vật lý chụp tối đa 3 ảnh: gần (5–10 m), xa (15–25 m), lệch góc. Ưu tiên nhiều biển khác nhau hơn nhiều ảnh của cùng một biển.
- Đa dạng điều kiện: nắng, râm, chiều tối, sau mưa, biển bẩn/phai, bị cây che một phần.

| ID | Mã | Gợi ý nơi tìm |
| --- | --- | --- |
| 0 | P.127 (50) | Đường nội đô lớn |
| 1 | P.127 (60) | Đại lộ, đường vành đai |
| 2 | P.127 (80) | Cao tốc, đường dẫn cao tốc; có thể khó tìm trong nội đô |
| 3 | P.125 | Quốc lộ, cầu |
| 4 | P.122 | Giao lộ hẻm ra đường lớn, đường ray; thường hiếm |
| 5 | P.102 | Đầu đường một chiều |
| 6 | W.245a | Trường học, khu dân cư |
| 7 | W.227 | Công trình đào đường, metro |
| 8 | R.301a | Giao lộ có phân làn |
| 9 | R.301e | Dải phân cách, đảo giao thông |

Nếu một lớp không tìm đủ mẫu, ghi rõ trong báo cáo. Không đưa ảnh GTSRB hay ảnh lấy từ Internet vào val/test cho đủ số: validator yêu cầu đủ 10 lớp ở mỗi split chính là để phát hiện thiếu hụt này.

## Cách chụp

- Dùng camera điện thoại ở độ phân giải gốc, khung ngang, giống góc nhìn người tham gia giao thông. Không zoom số, không crop.
- An toàn trước hết: đứng trên vỉa hè hoặc dừng xe hẳn; không chụp khi đang lái.
- Tránh chụp rõ mặt người và biển số xe. Nếu không tránh được, không chia sẻ ảnh ra ngoài nhóm. Không tải lên dịch vụ công khai.
- Mỗi buổi chụp là một **phiên**. Mỗi giao lộ hoặc đoạn phố dài khoảng 200 m là một **nhóm địa điểm**.

## Metadata

Ghi `metadata.csv` cạnh dataset, mỗi ảnh một dòng:

```text
file,split,location_group,session,captured_at,latitude,longitude,device,physical_sign,notes
images/val/hcm_q1_s01_0007.jpg,val,q1-le-loi-pasteur,s01,2026-10-12T16:40,10.77560,106.70110,Pixel 7,q1-lelo-p127-50-a,che 20% boi cay
```

`physical_sign` là mã nhóm tự đặt cho một biển ngoài đường. Mọi ảnh của cùng một biển phải nằm cùng một split. Tọa độ dùng để chia nhóm, không đưa vào nhãn YOLO.

## Gán nhãn

Dùng [CVAT](https://www.cvat.ai/) hoặc [Label Studio](https://labelstud.io/) chạy local. Roboflow tiện nhưng tải ảnh lên cloud, nên chỉ dùng nếu nhóm đồng ý về quyền riêng tư.

1. Tạo label list đúng **thứ tự ID** ở bảng trên, dùng đúng tên mã QCVN (ví dụ `P.127 (50)`).
2. Vẽ box sát viền biển, không gồm cột. Gán nhãn mọi biển thuộc 10 lớp còn đọc được, kể cả biển nhỏ ở xa. Biển nhỏ dưới khoảng 12 px hoặc không đọc được thì bỏ và ghi ở `notes`.
3. Không gán nhãn biển ngoài taxonomy; ảnh chỉ có biển ngoài taxonomy dùng file label rỗng.
4. Export dạng YOLO (CVAT: "YOLO 1.1"; Label Studio: "YOLO"). Mỗi dòng là `class_id x_center y_center width height`, chuẩn hóa 0–1.
5. Người thứ hai kiểm tra ngẫu nhiên khoảng 20% ảnh: sai lớp, thiếu box, box lệch.

## Chia split theo địa điểm

Chia theo `location_group` (hoặc theo `session` nếu mỗi phiên ở một khu khác nhau), **không chia ngẫu nhiên từng ảnh**. Hai ảnh liên tiếp của cùng một biển gần như giống nhau; nếu một ảnh ở train và ảnh kia ở test, metric sẽ ảo.

- Khoảng 60% nhóm cho train, 20% cho val, 20% cho test. Đổi nhóm giữa các split cho đến khi mỗi split có đủ 10 lớp.
- Train chưa dùng cho baseline, nhưng validator bắt buộc phải có và nó sẽ dùng cho lần fine-tune sau.
- Chốt test một lần rồi giữ nguyên qua các lần train. Không xem kết quả test để chỉnh ngưỡng hay chọn checkpoint.

Layout, đặt ngoài git (`data/field/` đã nằm trong `.gitignore`):

```text
data/field/pilot_v1/
  data.yaml
  manifest.json          {"kind": "vn_field_pilot_v1"}
  metadata.csv
  images/train/  images/val/  images/test/
  labels/train/  labels/val/  labels/test/
```

```yaml
path: .
train: images/train
val: images/val
test: images/test
names: ["P.127 (50)", "P.127 (60)", "P.127 (80)", "P.125", "P.122", "P.102", "W.245a", "W.227", "R.301a", "R.301e"]
```

## Kiểm tra và đánh giá baseline

```powershell
# Kiểm tra layout, taxonomy, nhãn, box và ảnh trùng giữa splits; không cần Ultralytics.
python -m ai_engine.train_detection validate --data data/field/pilot_v1/data.yaml

# Chấm checkpoint đang tích hợp trên val và test.
.\.venv-yolo\Scripts\python.exe -m ai_engine.train_detection evaluate --data data/field/pilot_v1/data.yaml --model ai_engine/checkpoints/detection/best.pt --imgsz 640 --batch 8 --device 0 --output runs/detection/field_baseline_01
```

`runs/detection/field_baseline_01/detection_report.json` có precision, recall, mAP50, mAP50–95 tổng và theo lớp, cùng SHA256 của dataset và checkpoint. Confusion matrix và các curve nằm trong `evaluate_val/` và `evaluate_test/`. Máy không có CUDA dùng `--device cpu`.

Precision/recall trong report được tính tại ngưỡng cho F1 cao nhất trên chính split đó, không phải ngưỡng API 0,65. Dùng chúng để so sánh giữa các checkpoint. Khi báo cáo chất lượng ở ngưỡng đã chốt, đọc giá trị tại ngưỡng đó trên curve precision/recall của test.

## Chọn lại ngưỡng confidence

1. Chỉ dùng `evaluate_val/`: xem `BoxF1_curve.png`, `BoxP_curve.png`, `BoxR_curve.png`.
2. Chọn ngưỡng ưu tiên precision, vì detection sai làm user mất công bỏ chọn và manager mất công duyệt. Mục tiêu trong kế hoạch là precision ≥ 0,85, recall ≥ 0,80; nếu không đạt cả hai, chọn precision và ghi recall thực tế.
3. Đặt `$env:SIGNSIGHT_YOLO_CONFIDENCE = '<ngưỡng>'`, khởi động lại backend, rồi kiểm tra `/api/v1/ai/status` trả `yolo.confidence_threshold` đúng giá trị.
4. Sau đó mới đọc test một lần và ghi kết quả.

## Báo cáo

Ghi `docs/qa/field_baseline_<ngày>.md` gồm:

- Số ảnh và số box theo lớp và theo split; các lớp thiếu.
- SHA256 dataset và checkpoint.
- Metric tổng và theo lớp trên val và test; ngưỡng đã chọn và lý do.
- Ví dụ lỗi điển hình: biển nhỏ ở xa, nhầm 50/60/80, false positive trên biển ngoài taxonomy.

Checkpoint hiện tại học từ ảnh crop biển Đức, nên baseline thấp là kết quả có giá trị, không phải lỗi quy trình. Bước tiếp theo là fine-tune trên train của tập này (có thể trộn GTSRB) và chấm lại trên đúng val/test đã chốt.
