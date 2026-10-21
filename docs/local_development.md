# Source và dữ liệu local

Repo source phát triển là checkout GitHub cố định, không đặt trong cache. Thư mục môn học cũ giữ tài liệu cá nhân, virtualenv và dữ liệu local; không đồng bộ từng file source giữa hai repo nữa.

Windows PowerShell, từ source repo:

```powershell
.\scripts\start_local.ps1 -DataRoot 'ABSOLUTE_PATH_TO_EXISTING_DATA_ROOT' -PythonPath 'ABSOLUTE_PATH_TO_PYTHON_EXE'
```

DataRoot là thư mục chứa backend/signsight.db, backend/uploads/images và ai_engine/checkpoints/detection/best.pt. Script dùng đường dẫn tuyệt đối và không sao chép dữ liệu sang source repo. Bỏ DataRoot khi muốn dùng dữ liệu mặc định trong checkout hiện tại.

Chạy tests từ source repo bằng Python môi trường đã cài requirements-dev. Frontend: npm ci, npm run test:frontend. Kiểm thử trình duyệt: npm run test:e2e (cần browser Playwright hoặc channel cấu hình).

Worklog, PDF, ảnh thực địa, credentials và dataset không đưa vào repo public.

Kiểm thử trình duyệt dùng backend tạm ở 127.0.0.1:8765, không dùng database ở cổng 8000. Thiết lập SIGNSIGHT_TEST_PYTHON nếu Python không có trong PATH. Local có thể đặt PLAYWRIGHT_CHANNEL=chrome để dùng Chrome đã cài; nếu không, chạy npx playwright install chromium. Project phone là viewport Chromium mô phỏng điện thoại, chưa phải nghiệm thu Safari/iPhone thật.
