# Chuẩn bị repo public

Tên đề xuất: `signsight`, nhánh `main`.

Repo làm việc phục vụ môn học có Word/PDF, worklog và ảnh QA trong lịch sử. Thêm vào .gitignore hoặc xóa trong commit mới không loại chúng khỏi commit cũ. Vì vậy bản public được xuất riêng, không mang theo thư mục .git cũ.

## Xuất source

Chạy từ repo làm việc:

```powershell
.\.venv-yolo\Scripts\python.exe -m scripts.prepare_public_repo --output .cache/github-public/signsight
```

Công cụ chỉ lấy các đường dẫn được cho phép từ danh sách Git, bỏ tài liệu môn học, toàn bộ QA screenshots/reports và runtime artifacts; thay ID Drive riêng bằng `YOUR_DRIVE_FILE_ID`. Dữ liệu gốc và repo gốc giữ nguyên. Đích phải là thư mục mới bên trong workspace; công cụ không ghi đè bản đã xuất, không init Git và không tự push. Các file mới cần được Git theo dõi hoặc không bị ignore để được lấy; luôn kiểm tra manifest in ra trước khi dùng.

Notebook Drive trong bản public cần điền ID nguồn riêng trước khi chạy. Không cấp quyền public cho dataset chỉ để chạy EDA; có thể mount Drive bằng tài khoản được cấp quyền.

## Kiểm tra và tạo lịch sử public

Trong thư mục public, chạy test như README. Kiểm tra nội dung trước khi stage. Chọn tên/email tác giả công khai; có thể dùng email noreply hiển thị trong GitHub Settings → Emails. Không tự suy ra email noreply khi chưa kiểm tra tài khoản.

```powershell
git init -b main
git config user.name 'YOUR_GITHUB_USERNAME'
git config user.email 'YOUR_GITHUB_NOREPLY_EMAIL'
git add .
git diff --cached --stat
git commit -m "chore(repo): initialize public SignSight source"
git status --short
```

Bản public chỉ có lịch sử mới, không chứa branch/tag trỏ về tài liệu cá nhân. Không thêm repo làm việc cũ làm remote hoặc push --mirror/--all từ repo đó.

## Push khi đã có URL

Tạo repository GitHub public tên `signsight`, để trống README/license/gitignore vì source đã có sẵn. Trong đúng thư mục public, thay URL mẫu bằng repo của bạn:

```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/signsight.git
git remote -v
git push -u origin main
```

CI chạy tự động sau push/PR. Không cần GitHub secrets để chạy tests. Công cụ chuẩn bị không chọn giấy phép thay nhóm tác giả; Leaflet giữ nguyên license riêng. Model và dataset không được phân phối cùng source.

Sau lần push đầu, clone repo GitHub vào thư mục phát triển riêng và làm việc tại đó; giữ thư mục môn học làm kho tài liệu riêng. Bản xuất trong .cache là bản bàn giao để push, không nên coi cache là bản sao lưu duy nhất.\n