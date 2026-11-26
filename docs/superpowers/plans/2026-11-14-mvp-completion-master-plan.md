# Kế hoạch tổng hoàn thiện MVP SignSight

> **Trạng thái: bản đề xuất để duyệt, chưa bắt đầu triển khai các đợt bên dưới.** Khi được duyệt, dùng superpowers:executing-plans và TDD cho từng thay đổi hành vi. Kế hoạch tổng chia thành các đợt độc lập; viết kế hoạch kỹ thuật chi tiết cho đợt được chọn trước khi sửa code.

**Goal:** Hoàn thiện một MVP đúng các luồng Alpha đã thống nhất: nhận diện ảnh, đóng góp có vị trí/bằng chứng, duyệt chất lượng dữ liệu, bản đồ/tuyến đường, và xác nhận lại dữ liệu quá hạn.

**Architecture:** Giữ FastAPI/SQLAlchemy/SQLite và kho ảnh riêng trên laptop, YOLO phía backend, Flutter cho user, web cho manager/admin. Tận dụng cơ chế auth, catalog/mapping, receipts, review, lifecycle và backup đang có; refactor từng phần với hợp đồng được kiểm thử. Web user cũ là công cụ kiểm tra tích hợp trong thời gian nghiệm thu native.

**Tech stack:** Python/FastAPI, Flutter/Dart, HTML/CSS/JavaScript, MapLibre/OpenFreeMap, Photon/OSRM, YOLO11s CAR35 V4, pytest/Node tests/Playwright.

**Spec:** Scope gốc gồm nhận ảnh/AI/GPS, nghi trùng, vòng đời và xác nhận lại, map/navigation, lịch sử và đánh giá AI. Kế hoạch Alpha 06/10 được user yêu cầu đối chiếu lại; mô tả kỹ thuật của scope được tóm tắt bên dưới. [PRODUCT.md](../../../PRODUCT.md) và [audit hệ thống](../../development/system_audit_2026-11-11.md) là nguồn đối chiếu hiện trạng, có mục cần cập nhật. Bản tham chiếu học thuật gốc là draft, không tự coi các ngưỡng/thời hạn đề xuất trong đó là rubric đã duyệt.

## 1. Phạm vi MVP đề xuất

| Mảng | Giữ trong MVP | Giới hạn |
|---|---|---|
| User | Flutter với Bản đồ, Đóng góp, Của tôi; đăng nhập/phân quyền | Android là mục tiêu nghiệm thu native trước; iOS/web điện thoại không được coi là đã nghiệm thu thay |
| Ảnh và AI | Chụp/chọn ảnh, YOLO, bbox/confidence, chọn biển, xác nhận nhãn và pin | Low confidence/không có detection có thông báo và đường thử lại; không tự công bố dự đoán |
| Duyệt | Staff xem bằng chứng/vị trí, chấp nhận/từ chối, giữ nhận xét và lịch sử | Giữ table + inspector hiện có; user không thấy công cụ quản trị |
| Map/route | Icon/ảnh chi tiết, lọc lớp/trạng thái, GPS, điểm đến, tuyến thật, nearby/corridor | Hiển thị biển gần tuyến; chưa bảo đảm biển áp dụng đúng chiều/làn của xe |
| Chất lượng dữ liệu | Nghi trùng có người duyệt; quá hạn tạo nhu cầu xác nhận; report kèm bằng chứng và audit | Không tự gộp ứng viên trùng; quá hạn xác nhận không phải kết luận biển mất hiệu lực pháp lý |
| Lịch sử | Trạng thái đóng góp/report, nhận xét, mở đúng biển đã duyệt | Làm mới khi quay lại màn hình hoặc bằng nút tải lại; chưa cần push |
| Vận hành | Laptop chạy BE/web/YOLO, app kết nối được, backup/restore, hướng dẫn demo | Giữ SQLite và runtime ngoài Git; Docker/cloud/store release chưa bắt buộc |

Tạm gác: Jetson, dashcam liên tục, tracking video, bản đồ/sync offline đầy đủ, tự gửi nền, push, voice/turn-by-turn, bảo đảm hướng/làn, đổi database/framework và redesign toàn bộ UI. Gửi đề xuất thủ công khi detector bỏ sót là tùy chọn sau nghiệm thu đường hiện có, trừ khi kết quả test cho thấy nó cần thiết để hoàn thành luồng đã chốt.

Phạm vi gốc có 10 lớp, CAR35 là phần mở rộng sau đó. Đề xuất giữ dataset/model candidate CAR35 V4, không đổi split hoặc cắt output head để thu gọn MVP. Đợt 1 chốt danh sách lớp nghiệm thu và cách báo cáo nhóm lớp gốc/phần mở rộng; toàn bộ lớp đang hỗ trợ vẫn phải có mapping rõ ràng. Lớp thiếu bằng chứng cần được ghi giới hạn, không dùng metric tổng để che thiếu coverage.

## 2. Hiện trạng làm điểm xuất phát

- Auth boundary và legacy reads: `df385b0`; nearby/popup stale-state: `2aa63c9`.
- Upload/đóng góp retry theo mã, xử lý upload ngoài event loop: `993d5e6`.
- Deadline/cancel web, đối chiếu kết quả duyệt và giữ ghi chú trong tab: `4def2a2`.
- Bằng chứng gần nhất ngày 12/11: Python407 passed/3 skipped, JavaScript118 passed, web28 và Flutter browser10 passed. Đây là kết quả đã ghi nhận, chưa chạy lại vào ngày lập plan.
- Cơ chế recovery còn giới hạn: nháp web/ghi chú staff trong RAM; report user và sửa account/policy chưa có keyed replay tương đương đóng góp/duyệt. Ghi rõ giới hạn; chỉ mở rộng khi kiểm thử MVP chứng minh cần.
- CAR35 V4 hiện là bộ cần giữ. Lượt dọn trước đã bỏ payload split cũ/bootstrap, giữ manifest và báo cáo. Không tái tạo các bản sao dataset không cần thiết cho kế hoạch này.
- Chưa coi runtime cá nhân, checkpoint đang phục vụ, điện thoại thật, HTTPS/release hoặc remote CI là đã nghiệm thu chỉ dựa trên test giả lập.

## 3. Quy tắc thực hiện

1. Chỉ sửa app trong canonical checkout; dữ liệu/runtime/academic documents ngoài repo public được giữ riêng.
2. Thay đổi hành vi: viết test tái hiện -> chạy RED -> sửa tối thiểu -> GREEN -> regression phù hợp -> conventional commit. Refactor giữ hành vi dùng characterization/regression tests; không tạo test giả để ép RED cho việc chỉ đổi tổ chức code.
3. Browser tests dùng API/DB/ảnh tổng hợp riêng; smoke checkpoint thật cũng dùng runtime tạm. Không dùng tài khoản/dữ liệu cá nhân làm fixture.
4. Trước migration/activation trên runtime thật: backup đã kiểm tra, cấu hình/checksum rõ ràng và đường rollback. Không restore đè hoặc thay model đang phục vụ ngầm định.
5. Không đổi catalog IDs/class order, loại endpoint hoặc xóa code chỉ vì không thấy một import. Kiểm tra callers, routing, dynamic loads, notebook embedding và test trước.
6. Giữ test bảo vệ các lỗi A01–A05. Tối ưu chỉ khi có số đo hoặc đang cản demo; giới hạn phạm vi theo luồng MVP.
7. Một đợt có thể tạo vài commit nhỏ. Không tự push/tag, phát hành công khai hoặc ghi nhận giờ/đóng góp học thuật chưa xảy ra.

## 4. Các đợt triển khai và điều kiện hoàn thành

### Đợt 1 — Khóa scope và bản nghiệm thu

**Mục đích:** Có một danh sách kiểm tra duy nhất, chấm bằng kết quả quan sát được.

**Files:** `PRODUCT.md`, `mobile/PRODUCT.md`, `docs/runtime/core_completion.md`; tạo `docs/testing/mvp_acceptance.md`.

- [ ] Đối chiếu từng yêu cầu gốc với màn hình, endpoint, test và bằng chứng hiện có; gắn trạng thái có code / đã test giả lập / đã test thiết bị thật.
- [ ] Chốt lớp nghiệm thu và bảng nguồn dataset; phân biệt dữ liệu thầy cung cấp, dữ liệu public và ảnh tự thu thập/gán nhãn. Không tự coi dataset có sẵn thay thế yêu cầu tự thu thập nếu chưa được thống nhất.
- [ ] Chốt Android trước, web staff, runtime demo và lớp cấu hình cần kiểm tra; xác định model đang phục vụ qua thông tin không chứa secret.
- [ ] Kiểm tra lại toolchain Python/Node/Flutter và đường dẫn môi trường hiện có trước khi chạy lệnh; không giả định virtualenv cũ vẫn tồn tại hoặc tự tạo runtime mới thay dữ liệu đang dùng.
- [ ] Đóng băng các mục ngoài scope trong mục 1. Xác định ba kịch bản demo: đóng góp, map/route, xác nhận lại/report.

**Xong khi:** Mỗi yêu cầu có nơi kiểm tra và tiêu chí PASS/FAIL; các quyết định lớp/thiết bị/phạm vi được duyệt. Chưa cần sửa nghiệp vụ ở đợt này.

### Đợt 2 — Hoàn thiện các điểm còn vướng trong luồng MVP

**Files chính:** `mobile/lib/features/capture/capture_state.dart`, `capture_screen.dart`, `mobile/lib/models.dart`, `mobile/lib/api.dart`, `mobile/lib/features/map/map_state.dart`, `map_screen.dart`; web staff nếu luồng kiểm tra vị trí cần sửa.

- [ ] Ảnh nhiều biển: hiện Flutter gửi một detection rồi xóa nháp. Theo scope đề xuất, cho phép giữ ảnh/kết quả để gửi tiếp detection còn lại, mỗi biển có pin/xác nhận/mã gửi riêng; không upload lại ảnh và không gửi trùng detection đã hoàn thành. Chốt UX trước khi code.
- [ ] Route: lưu origin/destination và xử lý đổi corridor mà vẫn giữ điểm đến; nearby radius không làm mất route. Kết quả cũ/lỗi mạng không ghi đè yêu cầu mới.
- [ ] Staff kiểm tra vị trí bằng một thao tác xem map/link rõ ràng; so sánh vị trí hiện tại/đề xuất khi report sửa pin. Tái sử dụng renderer và hủy reads lỗi thời.
- [ ] Giữ UI gọn: ba tab user, một workspace staff; bộ lọc/tùy chọn phụ mở khi cần. Lịch sử/report/revalidation vẫn tìm được từ chi tiết biển hoặc Của tôi.
- [ ] Làm mới lịch sử khi quay lại foreground hoặc tải lại có giới hạn; user thấy quyết định và nhận xét, mở đúng record ID.

**RED/GREEN cần có:** ảnh có hai detection với hai pin, mất phản hồi ở biển đầu, mở lại nháp và gửi biển còn lại; đổi corridor khi request cũ đang tải; route/nearby độc lập; quyết định staff xuất hiện trong lịch sử.

**Xong khi:** Cả ba kịch bản demo thực hiện được qua app/web và test tạm; các sửa đổi không phá ownership, receipts, ảnh bằng chứng và phân quyền. Chỉ thêm manual fallback nếu được duyệt riêng sau bằng chứng test.

### Đợt 3 — Refactor có chọn lọc, giữ hợp đồng

**Cấu trúc đích:** Giữ `backend/`, `ai_engine/`, `mobile/`, `frontend/`, `training/`, `notebooks/`, `scripts/`, `tests/`, `docs/` hiện tại; không di chuyển toàn repo sang một layout khác.

- [ ] BE: endpoints lo HTTP/auth/schema; dịch nghiệp vụ/transaction còn nằm ở endpoint sang service khi đang sửa luồng đó. Gom phần lặp có cùng hợp đồng, giữ auth trước replay và receipt cùng transaction với hiệu ứng.
- [ ] Flutter: giữ controller/feature modules hiện có. Làm rõ ownership của capture/map/history, dữ liệu nháp và pending intent; không thêm state-management framework chỉ để refactor.
- [ ] Web staff: tách queue loading và inspector/review khỏi file lớn nếu việc đó giảm độ rối; giữ shared request/auth và UI table + inspector. Không thay thành một SPA mới.
- [ ] Web user cũ: ghi rõ vai trò test lab, không phát triển thêm tính năng user song song. Chưa xóa trang/endpoint khi native parity và caller migration chưa được kiểm tra.
- [ ] Training: dùng `training/` làm nguồn sinh notebook; hai notebook CAR35 EDA/train là lối dùng chính, tải bằng gdown. Giữ baseline/legacy có giá trị tái lập trong khu vực đã phân biệt, chỉ xóa phần chứng minh không có caller/giá trị provenance.
- [ ] Dọn dependency, script, alias và docs link không dùng sau kiểm tra tham chiếu và regression; giữ ảnh/DB/weights/manifests riêng. Không xóa hàng loạt test vì MVP nhỏ hơn.

**Xong khi:** Không đổi hành vi/ID/payload ngoài migration đã chốt; test phù hợp xanh và từng phần refactor có thể rollback độc lập. Không lấy việc giảm số file hoặc số dòng làm tiêu chí thành công.

### Đợt 4 — Nghiệm thu AI và độ tin cậy dữ liệu

**Files/tooling dùng lại:** `training/experiments/evaluate.py`, `training/experiments/car35.py`, `scripts/benchmark_demo.py`, công cụ activation hiện có; tests duplicate/lifecycle và report. Artifact ảnh/model/metrics đầy đủ giữ trong khu vực private.

- [ ] Đọc artifact V4 đã train: `best.pt`, cấu hình, class order, results và fingerprint dataset; xác minh checkpoint/catalog/mapping tương thích. Giữ checkpoint phục vụ cũ cho rollback.
- [ ] Chọn threshold/inference settings bằng validation; báo precision/recall/mAP50/mAP50–95, GT coverage, confusion và lỗi từng lớp. Chỉ chạy test sau khi khóa lựa chọn; không dùng test để chỉnh ngưỡng.
- [ ] Thu thập/gán nhãn bộ ảnh thực tế riêng, không lấy lại ảnh train/val/test; ghi nguồn/phiên chụp và điều kiện ảnh. Phân biệt evaluation development V4 với kiểm tra thực địa; lớp quá ít mẫu phải có ghi chú.
- [ ] Kiểm tra 0/1/nhiều biển, biển nhỏ/mờ/che khuất, ngoài scope và ảnh nền. Model không sẵn sàng có lỗi rõ; không thay bằng dự đoán giả.
- [ ] Lập mẫu đối chiếu nghi trùng có nhãn thủ công: cùng biển, khác biển cùng loại ở gần, khác loại ở gần. Báo đúng trùng/nhầm trùng/bỏ sót với cỡ mẫu, không chỉ test endpoint.
- [ ] TTL/report: dùng fixture thời gian để mô phỏng quá hạn; xác nhận được duyệt mới gia hạn; reject không đổi record; removal/damage/correction giữ được evidence và history; không tự gộp candidate.
- [ ] Smoke model được chọn trên runtime tạm qua upload -> inference -> submit -> review -> exact map record; ghi rõ lớp chưa được hỗ trợ tốt. Activation vào runtime thật là bước riêng sau backup/rollback.

**Xong khi:** Artifact tái lập được, có metric/lỗi/giới hạn và kiểm tra data-quality; các ngưỡng nghiệm thu AI được chốt trước đánh giá, không coi một mAP tổng hoặc accuracy CNN cũ là bằng chứng street detection đạt yêu cầu.

Đợt 4 có thể thực hiện trong lúc sửa/refactor đợt 2–3; activation cuối vẫn cần smoke tích hợp sau các thay đổi.

### Đợt 5 — Điện thoại thật và vận hành laptop

**Tooling dùng lại:** `scripts/start_local.ps1`, lệnh `backend.manage` backup/restore/migrate, `docs/runtime/deployment.md`, `docs/getting-started/flutter_user_app.md`.

- [ ] Bắt đầu bằng một lượt test thiết bị thật sớm để phát hiện lỗi toolchain/quyền/kết nối, rồi nghiệm thu lại trên bản build được chốt. Ghi thiết bị, OS, build và API origin.
- [ ] Camera/gallery chọn/hủy/từ chối; GPS từ chối/sai số thấp-cao; app bị đóng khi picker mở; mất mạng/restart/retry; logout/đổi tài khoản. Chụp/kiểm tra khi đã dừng xe.
- [ ] Hoàn thành ba flow trên dữ liệu thực: ảnh -> duyệt -> record; điểm đến -> route/corridor -> chi tiết; cần xác nhận -> report -> staff xử lý -> lịch sử cập nhật.
- [ ] Chốt debug LAN hay build release với trusted HTTPS phù hợp mục đích. Laptop start/stop bằng một launcher; cấu hình DB/ảnh/weights/catalog/mapping rõ ràng. Không dùng `--reload` cho bản demo chốt.
- [ ] Backup DB/evidence đúng runtime, giữ weights/catalog/mapping/config riêng; restore sang thư mục mới, kiểm tra hash và các phiên được thu hồi. Không ghi đè runtime đang dùng.
- [ ] Đo upload, inference, nearby/route và thời gian hoàn thành flow: warmup, thiết bị/mạng/kích thước ảnh, p50/p95 và tỷ lệ lỗi. Chỉ sửa nghẽn đã đo; thêm giới hạn inference hoặc tối ưu query nếu tải demo không đạt.

**Xong khi:** Có checklist thiết bị thật, log/video/ảnh riêng tư, số đo và restore drill. Test browser giả lập không thay cho phần này; chưa yêu cầu Play Store, iOS hoặc server cloud công khai.

### Đợt 6 — Khóa bản demo, CI và bàn giao

**Files:** `.github/workflows/ci.yml`, `README.md`, `PRODUCT.md`, `docs/runtime/core_completion.md`, các hướng dẫn chạy/nghiệm thu và model activation.

- [ ] CI chạy đúng release commit: Python/JS, Flutter analyze/tests/build, web + Flutter E2E, Android build và public-source policy. Tách BE/JS nhanh khỏi phụ thuộc Flutter build nếu sửa workflow; browser dùng artifact Flutter đã build.
- [ ] Xác minh remote CI khi chuẩn bị publish; không coi local PASS là Actions đã xanh. A01–A05 và các lỗi mới có regression giữ lại.
- [ ] Một hướng dẫn chạy chính, capability matrix có ngày/build, cấu hình model đã kiểm tra và các giới hạn được đồng bộ; sửa mô tả 10 lớp/35 lớp theo kết quả đã chốt.
- [ ] Demo script ngắn cho ba flow và ít nhất một tình huống lỗi/recovery. Ghi rõ runtime demo và tránh dữ liệu giả lẫn dữ liệu thực trong kết luận.
- [ ] Chuẩn bị APK/artifact/checksum và rollback; credentials/keystore/dataset/ảnh/weights không vào public Git. Chỉ push/tag/phát hành khi user yêu cầu.
- [ ] Paper/report/worklog dùng kết quả và công việc thực đã có bằng chứng, được quản lý trong khu vực tài liệu riêng; không tự bổ sung kết quả chưa đo.

**Xong khi:** Người khác chạy được theo hướng dẫn, demo lặp lại được, remote CI và build đã được xác minh, artifact/giới hạn/rollback rõ ràng; không còn lỗi nghiêm trọng chưa xử lý trong ba flow.

## 5. Thứ tự và cách duyệt

1. Duyệt scope/tiêu chí và các điểm bổ sung tối thiểu ở đợt 1–2.
2. Smoke điện thoại sớm; triển khai các sửa MVP của đợt 2 trước refactor rộng hơn.
3. Refactor từng phần đợt 3, trong khi thực hiện đánh giá V4 và data-quality ở đợt 4.
4. Nghiệm thu lại bản tích hợp, restore và benchmark ở đợt 5.
5. Khóa demo/CI/tài liệu đợt 6. Lỗi mới quay về đúng module, sửa bằng TDD rồi kiểm tra lại flow bị ảnh hưởng.

Lập lịch theo đầu ra từng đợt; chưa gắn ngày nộp hay số giờ đóng góp chưa được xác nhận. Tại thời điểm duyệt cần xác nhận: danh sách lớp nghiệm thu, hành vi ảnh nhiều biển, Android làm thiết bị chính, và kết nối demo LAN/HTTPS. Các lựa chọn trên là đề xuất của người lập plan, chưa được ghi nhận là quyết định đã duyệt.
