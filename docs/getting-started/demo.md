# Chạy và nghiệm thu MVP

User dùng Flutter Android hoặc preview `/app/`; manager/admin dùng `/web/management.html`.
Laptop chạy FastAPI, SQLite, kho ảnh và YOLO. Dùng runtime demo riêng với checkpoint/catalog/mapping
đã chọn, giữ database/ảnh/weights ngoài Git. Không cần Docker cho demo laptop.

## Chuẩn bị

1. Build web theo [hướng dẫn Flutter](flutter_user_app.md), hoặc cài APK ARM64 phù hợp điện thoại.
2. Chạy `scripts/start_local.ps1` với `-DataRoot`, `-PythonPath`, `-RuntimeProfile` nếu có,
   `-BindAddress 0.0.0.0` và cổng đã cấu hình trong APK. Không dùng `--reload` trong demo.
3. Laptop và điện thoại cùng mạng. API HTTP LAN dành cho APK debug; GPS trong web điện thoại cần HTTPS.
4. Đăng ký user và chuẩn bị staff đúng role. Không dùng tài khoản admin trong app user.
5. Backup DB + ảnh trước demo. Kiểm tra ảnh thử bằng model thực tế trước khi trình diễn;
   ảnh detector bỏ sót không thể gửi như một detection. Model không tự được cải thiện khi đóng gói APK.

## Ba luồng demo

| Luồng | Thao tác và kết quả cần thấy |
| --- | --- |
| Đóng góp → duyệt → bản đồ | User chụp/chọn ảnh, xem bbox, xác nhận/sửa nhãn và ghim, gửi. User thấy chờ duyệt. Staff xem ảnh/vị trí, duyệt. User mở từ lịch sử và thấy đúng record, icon/ảnh và vị trí. |
| Điểm đến → hành trình | Tìm/chọn điểm đến, xem tuyến, bấm Bắt đầu và cho phép GPS. Chấm vị trí cập nhật; kéo map rồi Theo dõi lại. Đổi phạm vi vẫn giữ tuyến. Kết thúc dừng GPS liên tục. |
| Báo cáo → xử lý | User gửi ảnh/nhận xét về biển hỏng, mất hoặc sai thông tin. Record cũ giữ nguyên khi chờ duyệt. Staff quyết định; user xem kết quả và ảnh/lịch sử liên quan. |

Khi cần kiểm tra chụp/GPS thật, thực hiện lúc đứng yên hoặc với người thử ở ghế phụ.
Tuyến/hành lang chỉ là biển gần tuyến; chưa xác định chiều/làn áp dụng. Thời gian hiển thị là ước tính
toàn tuyến lúc lập kế hoạch, chưa có chỉ dẫn rẽ, ETA còn lại hoặc tự tìm tuyến mới khi đi lệch.

## Kiểm tra lỗi trước buổi demo

- Từ chối GPS/camera; vẫn dùng được màn hình khác và ghim thủ công cho đóng góp.
- Ảnh không có detection: thông báo rõ, giữ đường chọn ảnh/thử lại; không tự tạo biển.
- Mất mạng hoặc mất phản hồi gửi: thử lại đúng thao tác, không tạo đóng góp trùng.
- Model đang bận: giữ ảnh và thử lại sau thông báo; không bấm liên tục.
- Đăng xuất/đổi tài khoản: không hiện ảnh nháp, tọa độ hoặc kết quả của người trước.
- Provider map/search/route lỗi: app còn dùng được đóng góp/lịch sử; thử lại khi mạng ổn định.

## Vận hành và bàn giao

[Deployment](../runtime/deployment.md) hướng dẫn giới hạn inference, kiểm kê chỉ đọc,
backup/restore, TLS và signing. [Trạng thái nghiệm thu](../runtime/core_completion.md) phân biệt
test tự động với kết quả thiết bị thật. Các file backup/report có dữ liệu riêng phải để ngoài repo public.

APK debug LAN không phải bản phát hành store. HTTPS được tin cậy, ký release và kiểm thử Android thật
cần hoàn tất trước khi bàn giao cho người dùng bên ngoài. iOS cần macOS/Xcode/signing và nghiệm thu riêng.
