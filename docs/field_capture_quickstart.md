# Chụp ảnh thật với SignSight

Cập nhật 20/10/2026. Luồng hiện tại nhận diện **từng ảnh**, không phải video trực tiếp. Model vẫn là YOLO11n học GTSRB ROI với 10 lớp; chưa train trên dataset ViTSD mới và chưa được nghiệm thu bằng iPhone thật.

## Thử ngay trong cùng Wi-Fi

Tại thư mục gốc dự án, nếu server chưa chạy:

```powershell
.\.venv-yolo\Scripts\python.exe -m backend.manage migrate
$env:SIGNSIGHT_YOLO_DEVICE = '0'
.\.venv-yolo\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Máy không có CUDA dùng `cpu`. Giữ máy tính bật và terminal chạy. Dùng `ipconfig` lấy IPv4 Wi-Fi của máy tính; tại thời điểm kiểm tra là `192.168.1.98`, IP có thể thay đổi.

1. Trên iPhone cùng Wi-Fi, mở Safari: `http://192.168.1.98:8000/web/observations.html`. Đăng nhập tài khoản hiện có; tài khoản được dùng chung giữa các trang trên cùng địa chỉ trình duyệt đó.
2. Ở **Chụp ảnh → nhận diện bằng YOLO**, chạm ô chọn ảnh. Trình duyệt được yêu cầu dùng camera sau; tùy thiết bị có thể hiện hộp chọn ảnh. Chụp và xác nhận để tự upload, gọi YOLO, vẽ khung và hiển thị nhãn/confidence.
3. Có thể thử lại ảnh khác ngay tại cùng ô. Nếu YOLO lỗi sau upload, dùng **Detect bằng YOLO** để thử lại trên ảnh đã lưu.
4. Chỉ khi cần đóng góp: xác nhận nhãn, tọa độ từng biển rồi gửi duyệt. Manager duyệt xong biển mới xuất hiện trên bản đồ. Nhận diện đơn thuần không tự tạo biển trên bản đồ.

Nếu không vào được từ điện thoại, thử địa chỉ đó trên máy tính trước; kiểm tra cùng Wi-Fi, mạng khách có chặn kết nối thiết bị và quyền Windows Firewall của Python. Không mở cổng router ra Internet cho lượt thử này.

HTTP qua IP LAN không hỗ trợ GPS trình duyệt. Để thử GPS, làm phần HTTPS trong [hướng dẫn iPhone/iPad](iphone_ipad_testing.md), hoặc nhập tọa độ thủ công khi gửi duyệt. Thuộc tính camera file input khác API live camera `getUserMedia`; hành vi thực tế vẫn cần kiểm tra trên thiết bị. Tham khảo [HTML capture](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture) và [yêu cầu secure context của Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition).

Ảnh phải là JPEG/PNG/WebP, tối đa 10 MiB và 16 triệu pixel. Dùng chế độ ảnh 12 MP; nếu nhận được HEIC thì đổi sang JPEG. Không crop mất bối cảnh để làm đẹp kết quả.

## Lượt thử đầu: 20 ảnh, chưa cần gán nhãn toàn bộ

Chọn khoảng 5 biển thật thuộc 10 lớp trong [giao thức thực địa](field_dataset_protocol.md), mỗi biển 3 góc nhìn: gần, xa, lệch góc. Thêm 5 ảnh đường phố/bảng quảng cáo hoặc biển ngoài 10 lớp để kiểm tra nhận nhầm. Đứng ở nơi an toàn khi chụp.

Giữ ảnh gốc trên điện thoại hoặc trong `data/field/` (đã được Git bỏ qua). Ghi tên ảnh, địa điểm/phiên chụp, biển thực tế, model tìm đúng/bỏ sót/nhầm nhãn và thời gian chờ ước lượng. Đây là kiểm tra định tính ban đầu, chưa phải precision/recall vì chưa có ground truth đầy đủ. Ảnh không có detection vẫn cần giữ lại; chúng thường không tạo observation.

Để so sánh model mới công bằng, dành riêng một nhóm địa điểm cho đánh giá và không dùng ảnh nhóm đó để train/chỉnh ngưỡng. Gán nhãn và đo đầy đủ ở bước tiếp theo theo giao thức thực địa.

## Dataset ViTSD cải thiện gì và còn chặn ở đâu?

Dataset mới có 39.708 ảnh đường phố và 100 lớp khai báo, phù hợp hơn ảnh crop GTSRB cho việc tìm nhiều biển nhỏ trong cùng ảnh. Đọc review EDA (tài liệu nội bộ, không kèm bản public) để phân biệt thống kê toàn inventory với mẫu 3.000 ảnh.

Thứ tự thực hiện:

1. Tạo bản dữ liệu dẫn xuất: xác minh hash toàn bộ, xử lý nhãn lỗi `16031.txt`, chia nhóm theo cảnh/video/địa điểm. Toàn bộ 4.706 ảnh test có ứng viên trùng tên và kích thước với train/val; mới xác nhận trùng byte ở hai cặp trong mẫu hash. Chưa dùng test gốc để tuyên bố chất lượng.
2. Fine-tune detector trên dữ liệu đường phố sạch qua `scripts/local_detection_pipeline.py`, giữ checkpoint mới riêng. Kiểm tra recall biển nhỏ và lỗi giữa các lớp; ảnh nguồn nhỏ không tự có thêm chi tiết chỉ vì tăng kích thước đầu vào.
3. Rà ý nghĩa 100 nhãn và ánh xạ sang danh mục QCVN của hệ thống trước khi tích hợp. Backend hiện kiểm tra đúng thứ tự 10 lớp, frontend cũng chỉ có 10 lựa chọn; không thể chép checkpoint 100 lớp đè vào `best.pt` rồi sử dụng đúng ngay.
4. So sánh model cũ/mới trên nhóm ảnh thực địa độc lập đã gán nhãn, ở cùng ngưỡng/điều kiện đo đã chốt. Chỉ thay checkpoint phục vụ khi kết quả và mapping đã được kiểm tra.

Tải dataset hoặc chạy EDA không cập nhật model và không thêm biển lên bản đồ. Ảnh thực địa kiểm tra model; các đóng góp đã duyệt mới cung cấp tọa độ biển cho bản đồ.
