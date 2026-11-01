# Đề xuất refactor SignSight — 01/11/2026

Trạng thái: **bản đề xuất để review; chưa thực hiện xoá, di chuyển hoặc thay model**. Source được khảo sát tại commit `521c240`; `mobile/DESIGN.md` đang có thay đổi riêng, cần giữ nguyên.

## Mục tiêu

Một lối vào rõ ràng cho mỗi việc: Flutter cho user, web cho staff, FastAPI cho nghiệp vụ, hai notebook SupSign cho EDA/train. Giảm notebook và công cụ lịch sử trùng chức năng; tách file lớn theo trách nhiệm. Không viết lại hệ thống hoặc thay đổi giao diện trong đợt dọn code.

## Hai cách đã cân nhắc

- **Dọn từng nhóm trong cấu trúc hiện có — đề xuất.** Giữ `backend/`, `frontend/`, `mobile/`, `ai_engine/` và URL hiện tại. Thay generator notebook trước khi bỏ bản gộp, sau đó xử lý CNN cũ và tách Flutter. Có thể review/revert mỗi commit; bảo vệ cache Colab đang dùng.
- **Chuyển toàn bộ sang `apps/` và `packages/`.** Cây thư mục đẹp hơn nhưng phải sửa launcher, đường dẫn static, Gradle/Flutter, CI, docs và import cùng lúc. Chưa có nhu cầu build độc lập đủ lớn để bù rủi ro; không chọn trong bản đề xuất này.

Đây là khuyến nghị của người lập plan, chưa phải lựa chọn đã được user duyệt.

## Bằng chứng khảo sát

- 319 file tracked; 7 notebook. Hai notebook mới EDA/train vẫn được generator tạo thông qua bản gộp trung gian, nên xoá file notebook gộp chưa loại được code gộp.
- `mobile/lib/app.dart`: 1.624 dòng; chứa shell, map, capture, history, auth, pin picker, sign list, detection painter.
- `mobile/lib/controller.dart`: 832 dòng; chứa session, tìm điểm/tuyến, đóng góp/draft, history/feedback và các guard request.
- `frontend/index.html`: 586 dòng; HTML, CSS và JavaScript inline. `management.js`: 285 dòng; không cần framework mới chỉ để chia file.
- `scripts/generate_supsign_notebook.py`: 548 dòng; `supsign_training.py`: 473 dòng. Recipe chứa hash của file code và reader; đổi nội dung/import cũng có thể làm cache bị từ chối.
- `ai_engine/inference.py` và `model.py` không phải file chết: hai endpoint classify và `/ai/status` còn import classifier. Có nhánh heuristic cũ trong classifier, nhưng route hiện chặn khi không có model thật; không báo cáo nhầm thành lỗi API đang trả prediction giả.
- `ai_engine/config.py`, taxonomy và catalog vẫn được runtime import; ID cũ cần tồn tại để đọc dữ liệu lịch sử.
- `local_detection_pipeline.py`, `dataset_eda.py`, công cụ mapping/candidate, backup và các test bảo vệ phân quyền vẫn có caller hoặc nhiệm vụ riêng. Không tự xoá theo số lượng import.

## Phạm vi đề xuất

1. Chỉ còn hai notebook ở luồng chính. Tách việc tạo notebook khỏi bản gộp; giữ EDA CPU, train GPU, gdown, xuất ZIP, cache/resume và test opt-in.
2. Retire năm notebook lịch sử cùng generator không còn cần, sau khi chuyển test/khả năng cần giữ. Git history lưu bản cũ; không thêm một thư mục archive lớn trong repo public.
3. Chuyển runtime sang YOLO-only cho **prediction mới**, có thông báo rõ cho endpoint CNN đã kết thúc; vẫn đọc được `engine=cnn`/`task=classification` trong dữ liệu cũ. Không xoá row/migration/taxonomy để dọn source.
4. Tách Flutter theo màn hình và state sở hữu chức năng; giữ app facade/API, ba tab, IndexedStack và hành vi request/draft hiện tại.
5. Gom công cụ ML và docs theo nhiệm vụ, làm sau khi hợp đồng cache và notebook độc lập đã được kiểm thử. Không gom module runtime vào package training.
6. Web staff giữ nguyên. Web user được đánh dấu công cụ kiểm thử; chỉ bỏ khi parity test trên Flutter bao phủ map/route, góp ảnh, history, report và confirmation. Chưa đạt thì giữ, không xoá cho đủ số file.

## Cấu trúc đích

```text
signsight/
  backend/                         # API, schema, migrations, services; entry point giữ nguyên
  ai_engine/                       # detector, catalog, runtime config; giữ ID legacy
  frontend/                        # HTML entry point giữ URL, staff/shared assets
    shared/                        # auth, theme, catalog, sign links
    staff/                         # management CSS/JS theo chức năng
    lab/                           # web user chỉ di chuyển khi có alias và test URL
  mobile/lib/
    app.dart                       # facade/export SignSightApp, không chứa tất cả màn hình
    app/                           # shell, auth sheet, theme
    features/map/                  # map screen, pin picker, sign list
    features/capture/              # capture screen, detection overlay
    features/history/              # history và detail
    core/                          # API, stores và device services sau bước tách UI
  training/
    data/                          # audit, download, prepare, cache
    experiments/                   # train/evaluate và report
    notebooks/                     # builder EDA/train, cell fragments
    compatibility.py               # nhận cache recipe cũ theo allowlist rõ ràng
  notebooks/
    SignSight_SupSign_EDA_Colab.ipynb
    SignSight_SupSign_YOLO11s_Train_Colab.ipynb
  scripts/                         # launcher/build/check/benchmark, CLI wrapper mỏng
  tests/                           # chỉ nhóm sau khi bỏ import chéo test_* phụ thuộc path
  docs/                            # README chỉ đường; training/runtime/testing/development
```

Cây này là đích theo nhiều commit, không phải lệnh di chuyển một lần. `training/` chỉ tạo khi việc giữ cache V1 đã có test; trước đó giữ nguyên byte các module chuẩn bị hiện tại.

## Ràng buộc

- Chỉ source `signsight/` được refactor. Parent legacy source không đồng bộ theo.
- Dataset, DB, uploads, weights, credentials, giấy tờ/worklog/paper riêng không xoá, move hoặc commit trong đợt này. Thư mục train/EDA mới ở parent vẫn giữ nguyên.
- Không thay checkpoint, không tự tạo mapping QCVN, không renumber catalog hoặc sửa manifest đã dùng để train.
- URL `/api/v1`, `/web/management.html`, `/app/` và lệnh `python -m backend.manage`/uvicorn giữ hợp đồng. Thay endpoint CNN là ngoại lệ được nêu riêng, phải được duyệt như thay đổi chức năng.
- Read historical CNN rows; no database migration is required for pruning source.
- EDA/train phải upload lên Colab chạy độc lập, không clone repo, không private link/secret trong notebook public.
- Old cache recognition is explicit and read-only; unsupported recipe must fail. Code movement is not permission to bypass checksum or grouping checks.
- TDD cho thay đổi hành vi; refactor thuần dùng characterization test trước. Mỗi nhóm có commit riêng và rollback bằng revert source, không restore đè runtime.

## Ngoài đợt refactor

Checkpoint SupSign mới đã load/predict được nhưng thiếu mapping, thiếu field test và recall lớp quan trọng thấp. Rà nhóm dữ liệu/nhãn, train thí nghiệm mới và đo cảnh báo lái xe là luồng công việc riêng; không trộn vào commit dọn source. Báo cáo audit chi tiết được giữ ở workspace riêng, không đóng gói weights/ảnh vào tài liệu source public.

Không chuyển database, không thêm state-management/framework mới, không đổi API thành microservice, không đổi layout UI vừa làm.

## Tiêu chí nghiệm thu

- Luồng `EDA → cache → train → val/export` chạy được bằng fixture tổng hợp; cache cũ hợp lệ giữ nguyên split và manifest.
- User: auth → tìm điểm/map → ảnh/detect → sửa nhãn/pin → gửi → history; staff: duyệt → map; report/confirmation vẫn chạy. Tất cả browser tests dùng API tạm.
- Flutter giữ map khi đổi tab, draft tách theo account/origin và bỏ response muộn sau logout.
- API chạy được không có weights; detector lỗi minh bạch, không rơi về prediction heuristic.
- CI Python/JS/Flutter/E2E/build xanh; link/entry point hợp lệ. Không dùng giảm số test hoặc xoá test bảo vệ để đạt CI xanh.
- Một README chỉ đúng hai notebook chính và lệnh chạy hệ thống; các file bị bỏ có bảng chuyển đổi ở release note.
