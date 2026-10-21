# EDA dataset Google Drive

Notebook: [SignSight_Drive_Dataset_EDA_Colab.ipynb](../notebooks/SignSight_Drive_Dataset_EDA_Colab.ipynb).

Nguồn người dùng cung cấp: [archive.zip](https://drive.google.com/file/d/YOUR_DRIVE_FILE_ID/view). Đã xác nhận trang chia sẻ trả HTTP 200 và tên file ngày 20/10/2026; chưa tải/EDA toàn bộ dataset, chưa xác định số lớp hoặc cấu trúc nhãn thực tế.

1. Upload notebook lên Google Colab và chọn CPU runtime.
2. Chạy từ trên xuống. Mặc định gdown tải đúng file ID đã điền sẵn; không cần Kaggle key. Dataset được cache trong runtime và không giải nén.
3. Muốn dùng file gốc đã upload trên Drive: đổi `SOURCE_MODE='drive'`, sửa `DRIVE_ARCHIVE` theo vị trí thật của `archive.zip`, rồi cấp quyền mount. Ví dụ `/content/drive/MyDrive/datasets/archive.zip`. Không cần công khai file cho chế độ này và không phải copy ZIP vào runtime.
4. Mặc định `MAX_IMAGES=3000`, `HASH_LIMIT=1000`: kết quả là sample. Đặt `MAX_IMAGES=None` để scan mọi ảnh/nhãn, `HASH_LIMIT=None` để hash tất cả ảnh trong phạm vi scan. Bật `VERIFY_DECODE=True` khi cần kiểm tra giải mã đầy đủ.
5. Cuối notebook tự tải ZIP báo cáo về. Bật `SAVE_REPORTS_TO_DRIVE=True` nếu muốn giữ thêm báo cáo ở `MyDrive/SignSight/eda/reports`.

Output gồm inventory, metadata ảnh, box, thống kê lớp, issues, exact duplicates, hình phân bố và ảnh mẫu kèm bbox. Hỗ trợ YOLO detection TXT, Pascal VOC XML và COCO JSON; không tự nhận CSV/custom/segmentation thành detection labels. Class IDs được giữ riêng theo namespace, không gộp tùy tiện. Missing annotation không phải negative đã xác nhận. ZIP lồng/RAR/7z chưa đọc ảnh bên trong.

Report ViTSD ngày 20/10 cho thấy cùng ảnh có cả COCO JSON và YOLO TXT: auto đã đánh dấu ambiguous toàn bộ sample, nên chưa có thống kê bbox/lớp. Notebook cập nhật mặc định `ANNOTATION_FORMAT='yolo'`; có thể chọn `'coco'` để khảo sát riêng bản đó. Không gộp hai format hoặc tự fallback khi format đã chọn bị thiếu. Lựa chọn được ghi trong summary. Tải notebook mới rồi chạy lại các cell; ZIP đã tải trong cùng runtime vẫn được tái sử dụng, không cần tải lại. Kết quả kiểm tra report cũ (tài liệu nội bộ, không kèm bản public).

Chế độ download dùng [gdown 5.2.0](https://github.com/wkentaro/gdown/tree/v5.2.0) với resume và kiểm tra ZIP trước khi chấp nhận cache; file HTML/quota/login không được coi là dataset. Không đọc cookie trình duyệt. Nếu Drive chặn quyền hoặc quota, dùng mount bằng tài khoản có quyền. Cache cũ cùng ID được tái sử dụng; nếu thay nội dung file Drive, chọn đường dẫn `CACHE` mới để tải bản mới. Runtime Colab mới mất cache; Drive mount đọc bản gốc nên không cần tải lại.

Code dùng lại EDA helper đã có; notebook tự chứa code, không cần repo local. Chế độ mount xác định nguồn bằng đường dẫn, không xác minh file ID qua Drive API; summary ghi rõ điều này, nên kiểm tra đúng file trước khi đọc kết quả. Không train model hoặc sửa dữ liệu nguồn. Bộ kiểm thử dùng ZIP giả lập và mock download; chưa chạy Colab thật hoặc EDA toàn bộ ZIP Drive.

Kiểm tra hồi quy project ngày 20/10/2026: **211 test Python đạt** (bật YOLO thật) và **42 test JavaScript đạt**. Notebook được thực thi offline qua cả download mock và đường dẫn ZIP local/mount đến bước xuất CSV/JSON/plots/ZIP. Các kết quả này kiểm tra code, không đánh giá chất lượng dataset Drive.

Sinh lại và kiểm tra:

```powershell
.\.venv-yolo\Scripts\python.exe -m scripts.generate_drive_eda_notebook
.\.venv-yolo\Scripts\python.exe -m pytest tests/test_drive_eda_notebook.py tests/test_dataset_eda.py -q
```
