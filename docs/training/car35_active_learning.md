# CAR35 — thêm ảnh theo lỗi model

Vòng này dùng raw107 `best.pt` làm baseline. Pilot fine-tune chạy 15 epoch, AdamW 0.0003,
không flip và mosaic 0.1. [Notebook và cách chạy](car35_finetune.md).
Mục tiêu là thử hướng cải thiện; chưa bảo đảm tăng độ chính xác.

## Chọn ảnh để rà

Giữ ảnh mới trong một folder pool ngoài Git. Bắt đầu pilot khoảng 100–200 ảnh đa dạng nếu có:
biển tốc độ, người đi bộ, biển xa/gần, góc nghiêng, ánh sáng khác nhau và ảnh không có biển.
Ảnh chụp khi đứng yên/ở ghế phụ; giữ thông tin cảnh/chuyến/biển vật lý để chia nhóm.

```powershell
python -m training.experiments.active_learning --pool 'PHOTO_POOL' --review-pack 'REVIEWED_PACK.zip' --base-manifest 'RAW107_BASE_MANIFEST.json' --checkpoint 'RAW107_best.pt' --output 'ROUND2_review.zip' --device 0 --limit 100
```

`--review-pack` là gói đã review hiện tại, `--base-manifest` là manifest gốc raw107 cùng gói đó,
không phải manifest của dataset sau fine-tune. Mặc định checkpoint SHA-256 đã ghim theo baseline raw107;
đổi model cần chỉ định đúng `--checkpoint-sha256`. Không chạy trên serving DB hoặc sửa weights đang phục vụ.

Công cụ chạy inference 640px ở confidence 0.05, ưu tiên không detect, confidence thấp hoặc nhãn
cạnh tranh trên cùng bbox. Khoảng 25% suất dành cho chọn ngẫu nhiên từ phần còn lại để còn cơ hội
rà ảnh model tự tin nhưng sai. Đây là heuristic active learning, không phải bằng chứng ảnh đó có nhãn lỗi.

Ảnh trùng byte với val/test gốc bị loại; ảnh trùng trong pool/gói review được bỏ qua.
Ảnh mới được chuẩn chiều EXIF và lưu JPEG bỏ metadata. Ảnh train cũ giữ bytes/split/group.
Hash chỉ phát hiện trùng chính xác; dHash/capture-group screening vẫn chạy lúc chuẩn bị dataset fine-tune.

## Gói xuất ra

- Các ảnh/nhãn và dòng CSV đã review được giữ nguyên trạng thái.
- Ảnh mới có `reviewed=no`, `split=train`, group để trống nếu chưa có metadata.
- `labels/` là bbox AI gợi ý, đã bỏ bbox chồng lặp khác lớp. Phải kiểm tra mọi biển CAR35 trong ảnh.
  Nhãn rỗng từ model không có nghĩa đó là ảnh nền đã được xác nhận.
- `active_learning.json` ghi source hash, checkpoint, lý do chọn, predictions và suất exploration.
- Có thể truyền `--groups-csv` với cột `path,group`; path tương đối so với pool.

Giải nén, sửa nhãn khi cần, điền group thật và chỉ chuyển các dòng đã kiểm tra sang `reviewed=yes`.
Nén lại toàn bộ gói, chia sẻ qua gdown và đặt `REVIEW_URL` trong notebook. Các dòng train đã review
và giữ nguyên vẫn được chấp nhận. Ảnh mới được trộn vào dữ liệu cũ, không thay toàn bộ train bằng pool nhỏ.

## Đánh giá vòng tiếp theo

Giữ nguyên validation/test gốc trong pilot; đánh giá baseline/candidate trên cùng validation.
Đặt `REGRESSION_URL` bằng một ZIP nhỏ gồm ảnh lỗi để notebook xuất `photo_probe.json` ở confidence
0.35 và 0.05. Chỉ có danh sách lớp/confidence/bbox, không tự tính accuracy khi thiếu ground truth đầy đủ.
Ảnh đã dùng để sửa/train không còn là test độc lập. Cần thu riêng ảnh/cảnh/chuyến khác và khóa tập đó
trước khi chọn model. Không tự động kích hoạt candidate dựa trên mAP tổng.
