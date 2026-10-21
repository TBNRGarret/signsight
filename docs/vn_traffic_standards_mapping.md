# Đối Soát 10 Nhóm Biển Báo Giao Thông Dự Án SignSight Với Quy Chuẩn Việt Nam (QCVN 41:2019/BGTVT)

## 1. Cơ sở pháp lý và tiêu chuẩn áp dụng
- **QCVN 41:2019/BGTVT**: Quy chuẩn kỹ thuật quốc gia về báo hiệu đường bộ (Ban hành kèm theo Thông tư số 54/2019/TT-BGTVT).
- **Công ước Viên 1968 về Báo hiệu Đường bộ (Vienna Convention on Road Signs and Signals)**: Hệ thống biển báo Việt Nam và hệ thống biển báo châu Âu (nguồn gốc của tập dữ liệu GTSRB trong thư mục `archive`) đều tuân thủ chặt chẽ tiêu chuẩn quốc tế Vienna 1968 về hình dạng, màu sắc và biểu tượng.

---

## 2. Bảng ánh xạ 10 lớp biển báo SignSight $\rightarrow$ QCVN 41:2019

| ID Lớp | GTSRB ClassId | Mã QCVN 41 | Tên Tiếng Việt | Nhóm Biển | Độ tương thích thị giác | Ứng dụng thực tế trong Navigation tại VN |
|:---:|:---:|:---|:---|:---:|:---:|:---|
| **0** | 2 | **P.127 (50)** | Tốc độ tối đa cho phép 50 km/h | Biển cấm | 100% (Hình tròn, viền đỏ, nền trắng, số đen) | Cảnh báo tốc độ trong đô thị đường 2 chiều không dải phân cách giữa. |
| **1** | 3 | **P.127 (60)** | Tốc độ tối đa cho phép 60 km/h | Biển cấm | 100% (Hình tròn, viền đỏ, nền trắng, số đen) | Cảnh báo tốc độ trong đô thị đường đôi/có dải phân cách giữa. |
| **2** | 5 | **P.127 (80)** | Tốc độ tối đa cho phép 80 km/h | Biển cấm | 100% (Hình tròn, viền đỏ, nền trắng, số đen) | Cảnh báo tốc độ đường ngoài đô thị, quốc lộ, đường gom cao tốc. |
| **3** | 9 | **P.125** | Cấm vượt | Biển cấm | 100% (Tròn, viền đỏ, 2 ô tô con song song, ô tô vượt màu đỏ) | Cảnh báo an toàn trên các đoạn đường hẹp, đèo dốc, quốc lộ 1 làn xe. |
| **4** | 14 | **P.122** | Dừng lại (STOP) | Biển cấm | 100% (Bát giác đều viền trắng nền đỏ, chữ STOP trắng) | Bắt buộc dừng xe tại nút giao nguy hiểm, đường ngang đường sắt. |
| **5** | 17 | **P.102** | Cấm đi ngược chiều | Biển cấm | 100% (Tròn nền đỏ, vạch ngang màu trắng ở giữa) | Cảnh báo chống đi vào đường 1 chiều, tránh phạt nặng và tai nạn đối đầu. |
| **6** | 18 | **W.245a** | Đi chậm / Nguy hiểm khác | Biển cảnh báo | 95% (Tam giác viền đỏ, dấu chấm than `!` màu đen) | Cảnh báo đoạn đường hay xảy ra sự cố hoặc tai nạn bất ngờ. |
| **7** | 25 | **W.227** | Công trường đang thi công | Biển cảnh báo | 95% (Tam giác viền đỏ, người xúc đất màu đen) | Rất giá trị cho hệ thống: Biển tạm thời, cần kiểm tra định kỳ (Revalidation). |
| **8** | 35 | **R.301a** | Các xe chỉ được đi thẳng | Biển hiệu lệnh | 100% (Tròn nền xanh lam, mũi tên trắng hướng thẳng lên) | Cảnh báo hướng bắt buộc tại các giao lộ cấm rẽ. |
| **9** | 38 | **R.301e** | Đi vòng sang bên phải | Biển hiệu lệnh | 100% (Tròn nền xanh lam, mũi tên trắng chéo xuống bên phải) | Hướng dẫn vượt qua đảo giao thông, dải phân cách giữa. |

---

## 3. Lợi thế khi bổ sung dữ liệu sinh viên tự thu thập (Student-Collected Data)
1. **Dễ chụp thực tế**: Cả 10 loại biển này đều xuất hiện với mật độ rất dày đặc tại các tuyến đường xung quanh Swinburne Vietnam (Hà Nội, TP.HCM, Đà Nẵng).
2. **Khả năng kiểm chứng cao**: Sinh viên có thể dùng điện thoại chụp ảnh thật trên đường phố Việt Nam, gán tọa độ GPS thật để test tính năng:
   - Nhận dạng biển báo Việt Nam với model đã huấn luyện.
   - Thử nghiệm tính năng duplicate check (chụp cùng 1 biển ở 2 góc độ).
   - Thử nghiệm tính năng revalidation (biển công trường W.227 sau một thời gian thi công xong thì gỡ bỏ).
