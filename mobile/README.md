# SignSight user app

Flutter app dành cho user; admin/manager dùng web quản trị. Xem [hướng dẫn chạy và test](../docs/flutter_user_app.md).

Ba tab: **Bản đồ**, **Đóng góp**, **Của tôi**. API, dữ liệu biển, ảnh và inference vẫn nằm trên backend FastAPI. App không chứa checkpoint hoặc mật khẩu mẫu.

```bash
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter build web --release --base-href=/app/ --no-web-resources-cdn
```

Sau khi build, khởi động lại backend từ repo gốc và mở `http://127.0.0.1:8000/app/`. MapLibre JS/CSS được phục vụ từ `/web/vendor/maplibre/`; preview cần chạy cùng backend, không mở file HTML trực tiếp.

Android emulator: `flutter run -d <device-id> --dart-define=SIGNSIGHT_API_URL=http://10.0.2.2:8000`. Bản release yêu cầu URL HTTPS và cấu hình ký riêng trước khi phát hành.
