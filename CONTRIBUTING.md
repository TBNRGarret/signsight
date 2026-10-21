# Làm việc với repository SignSight

Tên repo: `signsight`. Nhánh chính: `main`. Repo Git nằm ngay thư mục project, độc lập với repository cha chứa các môn học khác.

Dùng Conventional Commits:

```text
feat(map): add route corridor filtering
fix(training): reject classes absent from training split
refactor(api): remove obsolete upload path initialization
test(auth): cover shared browser session expiration
docs(setup): explain local GPU training
chore(repo): exclude runtime artifacts and credentials
```

Commit mô tả thay đổi thực tế. Không tạo lịch sử/backdate hoặc gán tác giả cho người khác. Kiểm tra staged diff trước khi commit; dùng `git add <path>` cho những file liên quan.

Trước khi hoàn tất thay đổi backend/AI:

```powershell
.\.venv-yolo\Scripts\python.exe -m pytest tests -q
```

Frontend:

```powershell
node --test (Get-ChildItem tests/*.test.cjs).FullName
```

Kiểm thử YOLO thật là opt-in, cần checkpoint local và ảnh test GTSRB:

```powershell
$env:SIGNSIGHT_TEST_REAL_YOLO = '1'
.\.venv-yolo\Scripts\python.exe -m pytest tests/test_yolo_checkpoint_integration.py -q
Remove-Item Env:SIGNSIGHT_TEST_REAL_YOLO
```

Generator notebook cần được chạy lại sau khi sửa source; notebook là artifact phân phối nên giữ cả generator và `.ipynb`. Không loại file chỉ vì không có import: CLI, migrations, generators, test, tài liệu và báo cáo có entry point riêng.

Không commit `.cache`, môi trường Python, dataset gốc, model weights, database, ảnh user, API keys hoặc chứng chỉ/private key. Kiểm tra `git status --short` và `git diff --cached --stat` trước khi commit. Push/remote được cấu hình riêng khi có repository GitHub/GitLab phù hợp.

CI dùng Python 3.11, Node.js 24 và PyTorch CPU; không cần weights/dataset. Trên Linux/macOS dùng `python -m pytest tests -q` và `node --test tests/*.test.cjs`. Cài `backend/requirements-dev.txt` trước khi kiểm thử.

Chuẩn bị bản public theo [hướng dẫn GitHub](docs/github_preparation.md); không push repo môn học có tài liệu cá nhân trong lịch sử.
