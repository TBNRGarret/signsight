# Repository GitHub

Repo public: https://github.com/TBNRGarret/signsight, nhánh main.

Phát triển trực tiếp trong một checkout cố định ngoài .cache. Không xuất snapshot hoặc đồng bộ từng file từ thư mục môn học cho mỗi thay đổi. Tài liệu cá nhân, runtime, credentials, dataset và weights giữ ngoài Git.

Windows: scripts/start_local.ps1 hỗ trợ DataRoot/PythonPath để dùng lại dữ liệu và môi trường Python hiện có. Xem [hướng dẫn local](local_development.md).

Dùng Conventional Commits, chạy pytest, npm run test:frontend và npm run test:e2e trước khi chốt thay đổi. GitHub Actions kiểm tra Python, JavaScript và luồng browser bằng database tạm/model giả lập. Không cần model hay dữ liệu người dùng để chạy CI.

Công cụ scripts/prepare_public_repo.py chỉ dành cho xuất một bản source được chọn lọc từ repository cũ khi thực sự cần; không phải luồng phát triển thông thường. Không push --mirror hoặc đưa lịch sử repo môn học vào repo source.

Chưa gán giấy phép thay nhóm tác giả. Giữ license Leaflet và điều kiện sử dụng riêng của dataset/model.
