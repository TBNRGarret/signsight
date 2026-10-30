# App Flutter cho user

Đã có MVP trong `mobile/`, dùng chung FastAPI và database với web quản trị. YOLO chạy ở backend, nên cập nhật checkpoint tương thích sẽ phục vụ cả web và app. Không đưa model/dataset vào app.

## Giao diện và phạm vi

| Tab | Việc user làm |
| --- | --- |
| Bản đồ | Kéo/zoom MapLibre + OpenFreeMap, tìm điểm đến, xem tuyến ô tô và biển gần tuyến hoặc điểm đang xem. Danh sách mở khi cần, có lọc và tải thêm. |
| Đóng góp | Chụp/chọn ảnh → tự upload và detect → chọn biển trong ảnh → xác nhận nhãn → đặt/xác nhận ghim → gửi chờ duyệt. |
| Của tôi | Đóng góp có lọc trạng thái; xem ảnh/nhận xét và mở đúng biển được duyệt. Nút **Báo cáo & xác nhận lại** mở lịch sử báo cáo và danh sách biển cần kiểm tra. |

Một thanh tìm kiếm và một bảng tóm tắt trên bản đồ; không đưa các bảng công việc của staff vào app. Tài khoản và giao diện thiết bị/sáng/tối nằm trong menu góc trên. Lựa chọn theme hiện chỉ áp dụng trong lần mở app.

Tuyến bắt đầu từ **điểm đang xem trên bản đồ**. Dùng nút GPS trước khi tìm tuyến nếu muốn xuất phát từ vị trí hiện tại. Nút **Phạm vi tìm biển** chọn bán kính gần điểm 100–1.000 m và hành lang tuyến 20/50/100 m. Sau khi đổi phạm vi, chọn lại điểm đến để dựng tuyến mới. App chưa có dẫn đường từng chặng, theo dõi nền hay cảnh báo giọng nói.

User phải xác nhận nhãn và vị trí; tọa độ GPS/EXIF chỉ gợi ý. Ảnh thiếu GPS vẫn đặt ghim được. Khi detect lỗi, thử lại dùng ảnh đã lưu, không upload trùng. Sau khi gửi thành công, user xem trạng thái trong **Của tôi**; bản đồ chỉ hiện biển sau khi staff duyệt.

Chạm biển → **Báo cáo / xác nhận** để gửi ảnh hiện trạng và mô tả: còn tồn tại, bị gỡ, hư hỏng, sai vị trí, sai loại hoặc bổ sung bằng chứng. Loại biển lấy từ catalog backend. Báo cáo chờ staff duyệt; gửi báo cáo không tự sửa bản đồ. Thời hạn xác nhận là độ mới của dữ liệu, không kết luận hiệu lực pháp lý của biển.

Native lưu một bản nháp đóng góp trong thư mục riêng của app, tách theo API origin và tài khoản. Ảnh chưa upload do mất mạng được giữ để thử lại; ảnh đã upload dùng lại ID. Mở lại sau đăng nhập để khôi phục, kiểm tra nhãn/ghim rồi gửi. Logout/phiên hết hạn, bỏ nháp hoặc gửi thành công sẽ yêu cầu xóa nháp. Web preview dùng nháp RAM; form báo cáo cũng chỉ giữ ảnh/nhận xét khi trang còn mở. Đây chưa phải đồng bộ offline, hàng đợi nhiều ảnh hay tự gửi nền.

## Xem ngay trên laptop

Từ `signsight/mobile` (Flutter stable 3.47.7, Dart 3.13.5):

```powershell
flutter pub get --enforce-lockfile
flutter build web --release --base-href=/app/ --no-web-resources-cdn
```

Nếu SDK ở thư mục Windows có dấu cách và test gặp lỗi native hooks, dùng đường dẫn ngắn của SDK, ví dụ máy hiện tại:

```powershell
& 'C:\Users\WINDOW~1\flutter\bin\flutter.bat' test
& 'C:\Users\WINDOW~1\flutter\bin\flutter.bat' build web --release --base-href=/app/ --no-web-resources-cdn
```

Khởi động lại backend sau lần build đầu tiên để mount `/app/`, rồi mở:

- App user: `http://127.0.0.1:8000/app/`
- Web manager/admin: `http://127.0.0.1:8000/web/management.html`

Dùng tài khoản **user** (hoặc đăng ký trong app). Tài khoản owner/admin dành cho web quản trị. Preview dùng cookie HttpOnly cùng origin với web, không lưu bearer token/mật khẩu vào browser storage. Chỉ marker đăng nhập/đăng xuất không bí mật được chia sẻ giữa các tab. Native dùng kho bảo mật của hệ điều hành cho token, tách theo API origin.

Web preview ở địa chỉ HTTP LAN có thể không dùng được GPS; thử camera/GPS trên trình duyệt điện thoại cần HTTPS. Camera trên Flutter web do trình duyệt chọn hỗ trợ capture; không đồng nghĩa đã nghiệm thu camera Android/iOS native.

## Android trên laptop

Cài Android Studio, Android SDK/Command-line Tools và tạo emulator x86_64 có Google APIs hoặc Google Play. Build hiện tại cần Android SDK Platform 36, Build Tools 36 và **NDK (Side by side) 28.2.13676358**. Emulator có thể chạy API khác với compile SDK. CI dùng JDK 21; MapLibre cần Java 21 trở lên. Kiểm tra:

```powershell
flutter doctor -v
flutter doctor --android-licenses
flutter emulators
flutter devices
```

Backend ở máy host cần lắng nghe trên địa chỉ emulator truy cập được. Từ repo root có thể chạy trên `0.0.0.0` theo hướng dẫn local; không dùng database QA thay cho database cá nhân.

Từ `mobile/`:

```powershell
flutter run -d emulator-5554 --dart-define=SIGNSIGHT_API_URL=http://10.0.2.2:8000
```

`emulator-5554` là ví dụ ID từ `flutter devices`: thay đúng ID đang chạy, không thêm dấu `< >`. Sau khi build thành công, `flutter run` tự cài và mở app; giữ terminal để dùng hot reload.

### Nếu build báo thiếu NDK

Đọc phần `What went wrong` trước `BUILD FAILED`. Lỗi `sdkmanager did not install NDK 28.2.13676358` là thiếu SDK component, không phải bằng chứng code Dart lỗi. Trong Android Studio → SDK Manager → SDK Tools → **Show Package Details** → **NDK (Side by side)**, chọn đúng `28.2.13676358` rồi Apply.

Với Command-line Tools 23 dùng Android CLI mới, có thể cài trực tiếp bằng package ID dạng slash; không dùng lại wrapper `sdkmanager.bat` nếu wrapper tách nhầm `ndk;version` thành hai package:

```powershell
$android = Join-Path $env:LOCALAPPDATA 'Android/sdk/cmdline-tools/latest/bin/android.exe'
& $android --no-metrics sdk install 'ndk/28.2.13676358'
& $android --no-metrics sdk install 'platforms/android-36'
```

`flutter doctor -v` có thể báo SDK ở đường dẫn chứa dấu cách. Trên máy hiện tại, dùng alias Windows ngắn của **cùng thư mục** để không phải di chuyển SDK hoặc tải lại emulator:

```powershell
& 'C:\Users\WINDOW~1\flutter\bin\flutter.bat' config --android-sdk 'C:\Users\WINDOW~1\AppData\Local\Android\sdk'
```

Kiểm tra đường dẫn tồn tại trước khi áp dụng trên máy khác. `mobile/android/local.properties` là file local được Flutter tạo lại, không commit đường dẫn SDK cá nhân. Các dòng Java `WARNING: ... native access` không đồng nghĩa build fail; cần xem lỗi gốc ở phần `What went wrong`. Một số plugin còn dùng compile SDK 35; Gradle có thể cài thêm bản đó cạnh SDK 36.

Tham khảo [cài NDK theo phiên bản](https://developer.android.com/studio/projects/install-ndk) và [Android CLI](https://developer.android.com/tools/agents/android-cli).

### Nếu Kotlin báo `this and base files have different roots`

Windows có thể đặt project trên D: và Pub cache trên C:. Kotlin incremental compilation khi đó có thể lỗi `Could not close incremental caches` ở các plugin như MapLibre, image_picker hoặc package_info_plus. Project đặt `kotlin.incremental=false` trong `mobile/android/gradle.properties` để tránh lỗi relative path qua hai ổ; không tắt toàn bộ Gradle cache hoặc thay source plugin. Các task không đổi vẫn được Gradle bỏ qua và Dart hot reload vẫn hoạt động.

Lỗi đã được tái hiện bằng build thật trước khi áp dụng cấu hình. Nếu còn lỗi, giữ log `What went wrong`; không xóa SDK/Pub cache hoặc database để thử ngẫu nhiên. Xem [Kotlin incremental compilation](https://kotlinlang.org/docs/gradle-compilation-and-caches.html).

`10.0.2.2` chỉ dành cho Android emulator chuẩn. Thiết bị Android thật dùng IP LAN của máy host và cho phép cổng backend qua firewall. Bản debug cho HTTP local; bản release bắt buộc cấu hình API HTTPS:

```powershell
flutter build apk --debug --dart-define=SIGNSIGHT_API_URL=http://YOUR_LAN_IP:8000
```

CI tạo artifact **signsight-android-emulator-debug** (x86_64, API mặc định `10.0.2.2:8000`), dành cho emulator, không phải APK phát hành cho mọi điện thoại. Đăng nhập và ảnh được gửi về backend đã cấu hình, không có tài khoản mẫu trong app.

iOS có khai báo quyền camera/thư viện/GPS nhưng cần macOS + Xcode, cấu hình signing và chạy thiết bị thật để nghiệm thu. Chưa xác minh build iOS. Android camera/GPS, từ chối quyền và khôi phục ảnh sau OS đóng activity vẫn cần thử thật. App đã gọi `retrieveLostData` cho luồng đóng góp, có marker tài khoản để không lấy ảnh của phiên khác.

Release không dùng debug key. Cấu hình bốn biến `SIGNSIGHT_KEYSTORE_PATH`, `SIGNSIGHT_STORE_PASSWORD`, `SIGNSIGHT_KEY_ALIAS`, `SIGNSIGHT_KEY_PASSWORD` trong môi trường build, cùng `--dart-define=SIGNSIGHT_API_URL=https://YOUR_API_HOST`. Không commit khóa/mật khẩu; xem [Android signing](https://docs.flutter.dev/deployment/android). Chưa tạo khóa phát hành hoặc đưa app lên store.

## Xác nhận native local ngày 24/10/2026

Đã build APK debug x86_64 trên Windows sau khi cài NDK 28.2.13676358, SDK 36/35 và CMake 3.22.1, đồng thời tắt Kotlin incremental cache khác ổ. Đã cài và mở màn hình guest trên emulator Android 17/API 37, quan sát nền bản đồ và ba tab. Kiểm tra TCP từ UID app tới backend `10.0.2.2:8000` thành công; backend host trả HTTP 200. Đây là smoke test khởi động và kết nối, chưa nghiệm thu camera/GPS, luồng đóng góp native có đăng nhập hoặc chất lượng model trên ảnh thật. 22 test Flutter đạt và analyze không có issue.

## Kiểm thử

Cập nhật 30/10: trong tab **Đóng góp**, mở **Sửa loại biển nếu AI nhận sai** để chọn nhãn từ catalog backend và nhập lý do. Cần xác nhận lại nhãn trước khi gửi. Đổi bbox sẽ xóa phần sửa của bbox trước; bản nháp giữ phần sửa cho tài khoản/API hiện tại. Lịch sử hiện nhãn đề xuất, còn nhãn AI gốc giữ ở backend để đối chiếu. Bản đồ chính giữ nguyên khi chuyển giữa ba tab để tránh hủy renderer lúc đang nạp.

```powershell
# mobile/
dart format --output=none --set-exit-if-changed lib test integration_test
flutter analyze
flutter test

# repo root, sau khi build web preview
python -m pytest tests/test_flutter_preview.py -q
npx playwright test -c playwright.flutter.config.cjs
```

Browser test tạo API/SQLite/ảnh tạm, detector tổng hợp và bản đồ fixture. Kiểm tra guest, đăng nhập, upload/detect, xác nhận nhãn và ghim, gửi, duyệt và mở đúng biển. Các test này không đo chất lượng checkpoint thật, không đọc credentials/database cá nhân. Flutter test còn kiểm tra phiên hết hạn, logout trong lúc upload, retry và bố cục 360/430/1000 px.

Native integration có bài `integration_test/user_flow_test.dart`. Chạy `python tests/browser_server.py` trong terminal riêng, rồi từ `mobile/` chạy `flutter test integration_test/user_flow_test.dart -d emulator-5554 --dart-define=SIGNSIGHT_TEST_API=http://10.0.2.2:8765`. Bài này dùng MapLibre native với style fixture, ảnh/GPS tổng hợp và tài khoản tạm; không được trỏ vào runtime cá nhân. Kết quả và giới hạn nghiệm thu được ghi trong [trạng thái core](core_completion.md).

Nếu Playwright chưa có Chromium, chạy `npx playwright install chromium`. Windows có thể dùng Chrome đã cài bằng `$env:PLAYWRIGHT_CHANNEL = 'chrome'` và chỉ định Python venv qua `SIGNSIGHT_TEST_PYTHON`.
