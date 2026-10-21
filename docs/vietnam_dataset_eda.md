# EDA hai dataset Việt Nam trên Colab

Mở [SignSight_Vietnam_Dataset_EDA_Colab.ipynb](../notebooks/SignSight_Vietnam_Dataset_EDA_Colab.ipynb) trên Google Colab, chọn CPU runtime rồi chạy lần lượt. Notebook tự chứa code, không cần clone repo hoặc tải ~30 GB về máy tính trước.

```python
ACTIVE_DATASETS = ['vitsdb', 'supsign']  # thiếu ổ đĩa: chạy một bộ trước
LOCAL_ROOTS = {}  # hoặc {'vitsdb': '/content/drive/MyDrive/datasets/vitsdb'}
USE_DRIVE = False
CACHE_DATASETS_ON_DRIVE = False
KAGGLE_LOGIN = False
MAX_IMAGES = None  # toàn bộ; 3000: khảo sát nhanh, báo cáo ghi rõ là sample
HASH_LIMIT = 2000  # mỗi bộ; None: toàn bộ, 0: bỏ qua
VERIFY_DECODE = False  # True: giải mã ảnh đầy đủ thay vì chỉ đọc header
```

Nguồn pin version 1: `trnghiutrng/supsign/versions/1` và `trnghiutrng/vitsdb/versions/1`, lấy slug từ metadata hai link thầy cung cấp. Metadata ghi khoảng 16 GB và 14,1 GB; chưa tải toàn bộ và chưa xác nhận số lớp/format thực tế. API công khai từng trả 403. Nếu tài khoản có quyền, bật `KAGGLE_LOGIN=True` để nhập qua prompt hoặc dùng Colab Secret `KAGGLE_API_TOKEN` theo [KaggleHub](https://github.com/Kaggle/kagglehub). Không dán token trực tiếp vào code/output. Token không tự cấp quyền dataset riêng.

Nếu vẫn bị từ chối, kiểm tra quyền với người chia sẻ hoặc tải qua giao diện Kaggle bằng tài khoản có quyền rồi đặt thư mục dữ liệu/ZIP vào `LOCAL_ROOTS`. Bật `USE_DRIVE` khi nguồn nằm trên Drive. Cache mặc định ở runtime; bật cả hai cờ Drive mới giữ cache dataset qua phiên mới. Drive và runtime cần đủ dung lượng riêng. Ảnh/nhãn trong ZIP được đọc tại chỗ, không giải nén thêm; RAR/7z/TAR và ZIP lồng chỉ được kiểm kê.

ZIP báo cáo gồm:

- `inventory.csv`: file trên filesystem và thành viên ZIP, có `storage_kind` để không cộng nhầm dung lượng archive với dữ liệu bên trong.
- `images.csv`: kích thước/mode, split suy ra từ thư mục, trạng thái annotation, số box và SHA-256 đã tính.
- `boxes.csv`: box hợp lệ, format/namespace/ID/tên lớp, tọa độ chuẩn hóa, diện tích và cạnh ngắn ước lượng khi resize.
- `class_counts.csv` / `.json`: số instances/ảnh theo dataset, namespace và lớp; không tự đồng nhất ID hai bộ.
- `issues.csv`, `summary.json`, `duplicate_groups.json`, `distributions.png`, `samples.png`.

Tải ZIP bằng `google.colab.files.download`; khi bật Drive có thêm bản sao trong `MyDrive/SignSight/eda/reports`. Chỉ đóng gói báo cáo, không kèm dataset hay credentials. CSV bảo vệ ô có tiền tố giống công thức spreadsheet bằng dấu nháy; JSON tên lớp giữ nguyên.

Hỗ trợ YOLO detection TXT 5 cột, Pascal VOC XML, COCO JSON. Segmentation TXT, LabelMe/CSV/custom cần kiểm tra tiếp theo inventory/issues. Ảnh thiếu nhãn không phải background đã xác nhận. `empty_annotation` chỉ nghĩa annotation đọc được nhưng không có object. Box lỗi không tính vào phân bố box hợp lệ. Các thống kê chỉ bao phủ ảnh/nhãn đã đọc; nếu chạy sample, chưa phải tổng dataset.

Hash phát hiện file giống hệt byte; chưa phát hiện ảnh nén lại, near-duplicates hoặc frame liên tiếp. Hash mẫu không chứng minh hết trùng. `split=unknown` chưa đủ để kết luận không rò rỉ train/test. Notebook không tự chia split, gộp nhãn, xóa file hay train model.

Code nguồn và lệnh kiểm tra:

```powershell
.\.venv-yolo\Scripts\python.exe -m scripts.generate_eda_notebook
.\.venv-yolo\Scripts\python.exe -m pytest tests/test_dataset_eda.py -q
```

Helper nằm trong `scripts/dataset_eda.py`. Sau sửa helper/cell phải sinh lại notebook. **11 test đạt**, gồm dữ liệu giả lập YOLO/VOC/COCO, ZIP, class map xung đột, trùng split và thực thi các cell thống kê/vẽ/export ở ba chế độ có nhãn, chỉ ảnh, không có ảnh hỗ trợ. Download Colab được mock khi test local; chưa chạy Colab thật hoặc EDA đầy đủ hai bộ. Kết quả fixture không dùng để kết luận chất lượng dữ liệu của thầy.
