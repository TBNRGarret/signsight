# Kế hoạch cải thiện hệ thống sau refactor — 01/11/2026

Scope sản phẩm: app Flutter cho người đi ô tô, web cho admin/manager, FastAPI quản lý evidence và các quyết định duyệt. Các đầu việc dưới đây là kế hoạch tiếp theo, không được tính là đã hoàn thành bởi việc dọn source.

## P0 — Làm model có bằng chứng trước khi kích hoạt

Run SupSign mới hợp lệ nhưng validation chỉ có 3 nhóm, test 2 nhóm; nhóm test lớn nhất chứa 12.036 ảnh. Các lớp tốc độ/cấm vượt/công trường có recall thấp; hai lớp không có GT holdout. Model mới chưa có mapping QCVN được rà hoặc tập ô tô độc lập.

1. **Rà grouping và nhãn.** Xuất danh sách group size, ảnh đại diện, liên kết tạo bởi filename/dHash; kiểm tra các cụm lớn và các ảnh cùng biển/đoạn quay. Ghi metadata chuyến xe/địa điểm/biển vật lý khi có. Tạo split mới có phiên bản; giữ nguyên artifact V3 để so sánh lịch sử. Không bẻ một group qua split để đạt tỷ lệ đẹp.
2. **Bổ sung lớp ưu tiên ô tô.** Ưu tiên tốc độ 40/50/60/70/80, cấm vượt, công trường; rà nhầm cấm chung/cấm ô tô và hướng trái/phải. Thu thập thêm cảnh độc lập thay vì nhân bản ảnh hiếm. Lớp chưa đủ dữ liệu được ghi rõ là chưa đánh giá được, không loại khỏi catalog chỉ để tăng mAP.
3. **Tập ô tô thực địa riêng.** Mục tiêu ban đầu 100–200 ảnh có nhãn, gồm biển xa/nhỏ, chói/mưa/tối, nhiều biển và ảnh không có biển; đây là mục tiêu thu thập, không phải lượng đã có. Người lái không thao tác chụp khi đang lái. Chia theo chuyến/địa điểm; chốt protocol trước khi xem metric model.
4. **Thí nghiệm có kiểm soát.** Giữ YOLO11s làm baseline; so 640 và kích thước lớn hơn khi lỗi biển nhỏ đã được xác nhận. Chỉ thay một nhóm yếu tố mỗi run. Giữ cùng validation để so sánh; đổi split thì là benchmark phiên bản mới. Epoch 18 của run hiện tại tốt hơn epoch cuối, nên không mặc định train lâu hơn sẽ tốt hơn.
5. **Operating point và provenance.** Report lưu số ảnh đúng split (không nhầm tổng dataset), per-class GT/TP/FP/FN, precision/recall ở confidence/IoU triển khai, manifest/checkpoint/content fingerprint, phiên bản thư viện. Chọn threshold bằng validation; test chỉ chạy sau khi chốt. Ngưỡng nội bộ ban đầu P≥0,85/R≥0,80 từng lớp là mục tiêu rà soát, không phải chứng nhận an toàn.
6. **Mapping và tích hợp trên bản sao.** Rà 35 tên theo ảnh/nhãn và nguồn tiêu chuẩn hợp lệ; bind mapping với hash checkpoint/catalog, giữ ID cũ. So model cũ/mới trên cùng tập có nhãn khi có thể. Chạy upload→detect→correction→duyệt→map trên DB/ảnh tạm trước khi thay serving config.

**Đầu ra:** split/manifest phiên bản mới, bảng lớp có/thiếu bằng chứng, báo cáo validation/test tách biệt, mapping đã review và quyết định kích hoạt hoặc giữ baseline. Không tự động chuyển checkpoint theo mAP tổng.

## P0 — Nghiệm thu app bằng thiết bị thật

1. Android thật: camera/gallery, hủy picker, mất quyền, quyền GPS bị từ chối, tọa độ kém chính xác; app vẫn cho pin thủ công rõ ràng.
2. Bản nháp: kill/reopen app khi upload/detect, mất mạng giữa các bước, retry không tạo ảnh/đóng góp trùng; logout/đổi user hoặc API origin không lộ draft cũ.
3. Full flow hai vai trò: user gửi → manager kiểm tra evidence/sửa nhãn theo quy trình → duyệt/từ chối → user xem kết quả và đúng biển trên map. Kiểm tra report/confirmation chứ không chỉ đóng góp mới.
4. Map thật: provider bị chặn/chậm, route search timeout, chuyển sáng/tối, xoay máy và đổi tab. Dùng được hành động đóng góp/lịch sử khi nền map lỗi.
5. Bản APK x86_64 là artifact emulator, không phải bản điện thoại ARM64 đã nghiệm thu. Tạo bản ARM64 phù hợp, HTTPS và ký phát hành trước nghiệm thu máy thật. iOS native cần môi trường macOS riêng; không tính Flutter web là nghiệm thu iOS.

**Đầu ra:** checklist pass/fail có thiết bị/OS/build, log không chứa credentials và ảnh minh chứng riêng. Emulator/browser hiện tại chỉ là một phần bằng chứng.

## P1 — Đúng ngữ cảnh người đi ô tô

- Hành lang tuyến hiện cho biết biển gần tuyến; chưa chứng minh biển áp dụng cho đúng chiều/làn xe. Bổ sung hướng nhìn/hướng áp dụng và độ tin cậy vị trí bằng evidence, rồi mới lọc/cảnh báo theo chiều di chuyển. Không suy ra giới hạn tốc độ đang áp dụng chỉ vì một marker nằm gần đường.
- Hiển thị rõ nguồn, lần xác nhận cuối, còn hiệu lực/cần xác nhận và độ chính xác vị trí. Biển do AI đề xuất luôn cần xác nhận; duyệt dữ liệu không có nghĩa chứng minh hiệu lực pháp lý hiện tại.
- Ưu tiên thao tác ít: một hành động đóng góp, tự upload/detect, sửa nhãn tùy chọn, xác nhận pin, gửi. Staff làm trong bảng/master-detail, user không thấy công cụ quản trị.
- Nếu làm thông báo khi di chuyển, trước hết cần test thứ tự biển, hướng, GPS nhiễu, chống lặp và giới hạn phân tâm. Đây là feature riêng; không bật cảnh báo lái xe chỉ dựa trên model hiện tại.

## P1 — Vận hành laptop đáng tin cậy

- Một lệnh start/stop có cấu hình rõ API/data/weights/catalog/mapping; health phân biệt API alive với detector ready. Chứng chỉ HTTPS phải được thiết bị tin cậy.
- Diễn tập backup/restore DB + evidence vào thư mục mới, kiểm tra image hashes và catalog identity, không restore đè dữ liệu đang chạy.
- Đo upload, inference, query nearby/route, trang duyệt: warm median/p95 và lỗi theo thiết bị/mạng. Ảnh trống smoke không phải benchmark latency sản phẩm.
- Đo query plan trước khi thêm index/bbox prefilter hay cache. Giữ SQLite khi đáp ứng tải demo; chỉ chuyển Postgres/PostGIS khi có dữ liệu đo và nhu cầu đồng thời/không gian cụ thể.
- Rà dependency/license dataset/model/provider và điều kiện dùng; không phân phối weights/dataset vào repo public. Policy scan read-only/CI là lớp bảo vệ bổ sung, không thay review nội dung.

## P2 — Phát hành và học thuật dựa trên bằng chứng

- CI: Python, JS, Flutter, hai E2E suites, Android build, public source policy; giữ fixture synthetic và kiểm thử checkpoint thật opt-in.
- Chốt demo script ngắn cho upload→review→map/report và tình huống lỗi; xác nhận dữ liệu demo thuộc runtime nào.
- Paper/report: phân biệt baseline GTSRB ROI, SupSign development split và car-field test; ghi hạn chế và metric từng lớp. Chỉ cập nhật worklog bằng công việc/giờ/thành viên thực tế.
- Phát hành theo tag và checklist rollback; giữ checkpoint/catalog/mapping/reports thành artifact riêng có checksum.

## Thứ tự bốn giai đoạn

| Giai đoạn | Việc chính | Điều kiện chuyển tiếp |
| --- | --- | --- |
| 1 | Chốt grouping/nhãn và protocol tập ô tô; smoke app thật | Có manifest/nhóm được review và danh sách lỗi thiết bị |
| 2 | Bổ sung lớp hiếm, train/validation thí nghiệm có kiểm soát | Có per-class coverage/threshold report, không chỉ mAP tổng |
| 3 | Mapping, tích hợp trên bản sao, test user/staff và backup/HTTPS | Full flow và rollback qua kiểm tra, rõ lớp chưa hỗ trợ tốt |
| 4 | Đo hiệu năng, khóa demo, cập nhật paper/report và release | Chỉ công bố kết quả có artifact và thiết bị/protocol đi kèm |

Đây là thứ tự ưu tiên, không gán ngày/giờ hoàn thành hoặc đóng góp thành viên chưa diễn ra. Hạng mục không đạt bằng chứng được giữ ở trạng thái thử nghiệm thay vì thêm feature để che khoảng trống.
