# SignSight Repository Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate unless separately authorized.

**Goal:** Giảm notebook/code lịch sử và chia module theo trách nhiệm mà giữ được cache Colab, dữ liệu lịch sử và các flow user/staff.

**Architecture:** Refactor tăng dần trong checkout `signsight/`, giữ runtime entry points. Thay notebook builder trước, retire CNN có tương thích đọc lịch sử, sau đó tách UI/state và gom tools; không di chuyển toàn bộ repo sang `apps/`.

**Tech Stack:** Python 3.11, FastAPI/SQLAlchemy/Alembic, Ultralytics 8.4.173, Jupyter JSON, Flutter 3.47.7, Node 24, Playwright.

**Spec:** [2026-11-01-repository-refactor-design.md](../specs/2026-11-01-repository-refactor-design.md)

**Status:** Draft for user review, chưa bắt đầu implementation. Các file đề xuất bỏ bên dưới là ứng viên có điều kiện, không phải kết luận tất cả đang unused.

## Global Constraints

- Chỉ source `signsight/` được refactor. Parent legacy source không đồng bộ theo.
- Không thay checkpoint, không tự tạo mapping QCVN, không renumber catalog hoặc sửa manifest đã dùng để train.
- Read historical CNN rows; no database migration is required for pruning source.
- Old cache recognition is explicit and read-only; unsupported recipe must fail.
- Không move/delete DB, uploads, weights, datasets, credentials, worklog hoặc paper; không stage `mobile/DESIGN.md` đang do user sửa.
- Giữ CLI/URL runtime và hai notebook upload độc lập. Mỗi task một commit, các module bị đổi phải có test trước và test hồi quy sau.

## Review Focus

- Cache đã tạo bằng code cũ vẫn restore đúng split, không bị thay manifest hoặc bị coi là cache mới sau move.
- Historical CNN rows vẫn đọc được dù không còn prediction CNN mới.
- Logout/đổi account khi request đang chạy không ghi nhầm draft hoặc hiển thị dữ liệu account cũ.
- IndexedStack giữ native map khi đổi tab; pin picker dispose không gây callback vào map đã huỷ.
- Import/CLI/static URL/doc link không phụ thuộc current working directory hoặc đường dẫn laptop riêng.

## Thứ tự và phạm vi

Làm Task 1–2 trước để giảm bối rối khi dùng notebook. Task 3 cần duyệt việc kết thúc API CNN. Task 4 chỉ tách mã, không redesign. Task 5–6 là đợt sau; không bắt buộc dồn hết thành một PR.

### Task 1: Chốt inventory, baseline và phạm vi cần giữ

**Files:** tạo `docs/development/repository-map.md`; khảo sát `README.md`, `.github/workflows/ci.yml`, `backend/app/main.py`, các launcher và test entry points. Chỉ ghi snapshot source vào `.cache/refactor_inventory/` nếu cần, không copy runtime.

**Interfaces:** đầu vào `git ls-files`, import/CLI/static reference; đầu ra bảng `path → callers → keep/replace/retire → replacement → verification`.

- [ ] Ghi HEAD và `git status --short`, lưu diff các file có thay đổi user vào vùng riêng. Không reset/stash cả workspace hoặc commit thay đổi user.
- [ ] Lập bảng đầy đủ 7 notebook/6 generator, CNN routes, GTSRB converters, generic YOLO evaluator, local Vietnam CLI và public exporter. Dùng import, CLI/docs, tests và dynamic notebook imports; không chỉ dùng grep không thấy tên.
- [ ] Chạy baseline Python, JS, Flutter analyze/test và browser flows bằng disposable fixture. Ghi lỗi có sẵn theo tên; không lấy số pass của audit trước làm kết quả hiện tại.
- [ ] Commit riêng `docs: map repository entry points and cleanup scope` khi bảng replacement đủ cụ thể. Đây là bước khảo sát, không thêm test mô phỏng nội dung Markdown.

### Task 2: Hai notebook độc lập, bỏ năm notebook cũ

**Files:** sửa `scripts/generate_supsign_notebook.py`, `tests/test_supsign_training.py`; tạo `tests/test_training_notebooks.py`, `notebooks/README.md`; cập nhật `docs/supsign_yolo11s_colab.md`, `README.md`. Chưa move `scripts/supsign_training.py`/`dataset_eda.py` vì recipe hash.

**Interfaces:** giữ `build_eda_notebook() -> dict`, `build_train_notebook() -> dict`; hai file `.ipynb` hiện tại; EDA xuất report/cache/checksum, train chỉ nhận prepared cache. Không gọi builder bản gộp làm bước trung gian.

- [ ] Viết test đỏ thực thi notebook EDA CPU bằng fixture, cấm import Torch/Ultralytics; xuất report không weights/full dataset. Trong runtime mới thực thi train từ cache, so manifest bytes/split và chặn checksum sai/nhãn chưa duyệt.
- [ ] Bổ sung kiểm thử artifact tải được theo đúng file path, generator chạy lại ra cùng nội dung và không cần bản notebook/generator lịch sử. Chuyển các test hữu ích từ notebook cũ: ZIP an toàn, checksum, label corruption, download interruption, output không overwrite. Không giữ assertion chỉ tìm literal text.
- [ ] Tách common cell builder/config/pipeline; EDA/train được dựng trực tiếp. Giữ thông số chỉnh được, validation/test opt-in, own-photo, resume và tự tải ZIP kết quả đang có.
- [ ] Khi các test replacement đã xanh, bỏ các notebook: `SignSight_Colab_Kaggle_Training.ipynb`, `SignSight_YOLO_Colab.ipynb`, `SignSight_Vietnam_Dataset_EDA_Colab.ipynb`, `SignSight_Drive_Dataset_EDA_Colab.ipynb`, `SignSight_SupSign_YOLO11s_Colab.ipynb`.
- [ ] Bỏ generator tương ứng `generate_notebook.py`, `generate_yolo_notebook.py`, `generate_eda_notebook.py`, `generate_drive_eda_notebook.py` sau khi dependency/test không còn cần. Giữ generic `dataset_eda.py` và local Vietnam CLI; xoá notebook không đồng nghĩa xoá reader YOLO/VOC/COCO.
- [ ] Dời hướng dẫn cần lưu sang release note ngắn, sửa mọi link và CI/export allowlist. Các test chỉ phục vụ notebook đã retire được bỏ sau khi bảo đảm test hành vi thay thế đã có; chưa xoá converter đang được generic evaluator hoặc smoke legacy dùng.
- [ ] Run: `python -m pytest tests/test_training_notebooks.py tests/test_supsign_training.py tests/test_colab_downloads.py tests/test_dataset_eda.py tests/test_local_detection_pipeline.py -q`, sau đó toàn bộ Python suite.
- [ ] Commit: `refactor(training): keep independent EDA and training notebooks`.

### Task 3: Retire CNN prediction, giữ được lịch sử

**Files:** `backend/app/api/v1/endpoints/images.py`, `signs.py`, `backend/app/core/upload_limit.py`, `backend/app/schemas/images.py`, `ai_engine/inference.py`, `model.py`, `train.py`, `config.py`, `.env.example`, `scripts/start_local.ps1`, `scripts/test_end_to_end_flow.py`, `tests/test_images_observations.py`, `tests/test_accounts.py`.

**Interfaces:** YOLO `/images/{id}/detect` không đổi. `/images/{id}/classify` và `/signs/classify` trả lỗi kết thúc chức năng rõ ràng (đề xuất HTTP 410 sau auth; user cần duyệt). `/ai/status` tạm giữ `cnn: {ready:false, retired:true, task:'cropped_image_classification'}` cho client cũ; `yolo` không đổi. Existing run/observation đọc được `cnn` + `classification`.

- [ ] Trước implementation, xác nhận trong phần review plan rằng CNN endpoint được retire. Nếu cần giữ client cũ, làm feature flag/deprecation trước; không tự xoá API chỉ để giảm file.
- [ ] Viết test đỏ: anonymous vẫn 401, authenticated gọi CNN nhận 410, detector không có weights nhận 503; không import/load classifier lúc startup. Historical run fixture `engine=cnn, task=classification, bbox=null` vẫn truy vấn/hiển thị được với đúng quyền.
- [ ] Tháo classifier import và nhánh heuristic; bỏ CNN model/train và generator đã được thay. **Giữ** `config.py`/`TAXONOMY`, legacy ID, schema read union và migration lịch sử. Không bỏ `/signs/register` trong cùng task vì có contract phân quyền riêng.
- [ ] Thay smoke script CNN/manual cũ bằng wrapper gọi flow YOLO disposable hiện có hoặc bỏ script cùng docs entry, giữ kiểm tra upload→detect→review→map, duplicates/lifecycle trong suite chuẩn.
- [ ] Rà dependency bằng import thực. Chuyển dependency chỉ phục vụ train/EDA ra `training/requirements.txt` khi Task 5 sẵn sàng; không gỡ Torch/Torchvision nếu YOLO environment còn cần.
- [ ] Run: `python -m pytest tests/test_images_observations.py tests/test_accounts.py tests/test_runtime_catalog.py tests/test_catalog_mapping.py -q`; toàn bộ Python và hai browser suites.
- [ ] Commit: `refactor(ai): retire CNN prediction while preserving historical runs`.

### Task 4: Tách Flutter theo màn hình, rồi mới chia state

**Files:** sửa `mobile/lib/app.dart`, `controller.dart`; tạo `mobile/lib/app/user_shell.dart`, `app/auth_sheet.dart`, `features/map/map_screen.dart`, `pin_picker.dart`, `sign_list.dart`, `features/capture/capture_screen.dart`, `detection_overlay.dart`, `features/history/history_screen.dart`, `contribution_detail.dart`. Giữ `app_theme.dart`/`ui_components.dart` đến khi import ổn định.

**Interfaces:** giữ `SignSightApp(controller:, mapBuilder:, devices:)`, `AppController` public facade, `MapBuilder`/`MapScene` và API payloads. Các screen nhận controller và callback đang có; không tự tạo một instance controller mới cho mỗi tab.

- [ ] Chạy/đảm bảo characterization test map retention, correction, pin, history, theme và narrow/large text hiện tại. Thêm ca cần thiết: auth modal đang mở khi logout; dispose pin picker lúc style đang load; late response sau đổi account.
- [ ] Tách widget theo trách nhiệm, từng màn hình một; giữ IndexedStack trong `UserShell`, keys/semantics/control labels và state sở hữu TextEditingController. `app.dart` export đúng public symbols mà test/entry point đang dùng.
- [ ] Chạy widget tests sau mỗi màn hình. Không đổi theme, spacing hoặc flow trong commit tách module.
- [ ] Tách state nội bộ sau UI xanh: tạo `features/map/map_state.dart`, `features/capture/capture_state.dart`, `features/history/history_state.dart`; facade giữ chữ ký API. Giữ một session generation dùng chung và thứ tự flush draft, không reset version guard theo tab.
- [ ] Run: `flutter analyze`, `flutter test`, build web với `--base-href=/app/ --no-web-resources-cdn`, `playwright test -c playwright.flutter.config.cjs`. Native smoke trên API tạm: đổi tab lúc map load, pin confirm, correction, submit/review/history.
- [ ] Commit UI extraction riêng `refactor(mobile): extract user screens without behavior changes`; state extraction là commit sau `refactor(mobile): isolate feature state behind app controller`.

### Task 5: Gom ML tools và ổn định hợp đồng cache

**Files:** tạo `training/data/{audit,downloads,supsign,cache}.py`, `training/experiments/{train,evaluate}.py`, `training/notebooks/{__init__,builder}.py`, `training/compatibility.py`, `training/requirements.txt`; sửa import/callers `scripts/supsign_training.py`, `dataset_eda.py`, `colab_downloads.py`, `local_detection_pipeline.py`, notebook generator; test `tests/test_training_compatibility.py` và các suite training hiện có.

**Interfaces:** các facade cũ giữ chữ ký `prepare_supsign`, `verify_dataset`, `pack_dataset`, `restore_dataset`, `train_experiment`, `evaluate_checkpoint` trong một giai đoạn. New `dataset_content_fingerprint(manifest: dict) -> str` hash tên/thứ tự lớp, source ZIP hash, ảnh/nhãn/group/split/recipe theo JSON canonical; bỏ `source_summary.root` khỏi **content fingerprint**, không thay checksum archive/manifest gốc.

- [ ] Viết test đỏ: cùng nội dung ở hai path cho content fingerprint giống nhau; đổi image/label/split/class/semantic recipe thì khác. Old manifest raw bytes và checksum được giữ nguyên. Unknown old recipe phải fail.
- [ ] Tạo fixture tổng hợp prepared-cache V1 trước khi di chuyển code. Legacy allowlist gồm đúng code/reader signature từng hỗ trợ, lấy từ provenance đã kiểm tra; không chấp nhận chỉ vì có cùng 35 tên. Test restore vẫn nguyên manifest/split; thử tamper cache/label phải bị chặn.
- [ ] Chốt recipe V2 cho cache mới và adapter đọc V1 rõ ràng. Không đổi recipe của cache đã train, không sửa `training_request.json` cũ và không bỏ kiểm tra hash để resume bằng config khác.
- [ ] Move implementation theo data/train/notebook; giảm scripts thành CLI wrappers. Không chuyển hết runtime `ai_engine/` sang training: detector/catalog vẫn ở app runtime.
- [ ] Giữ generic evaluator/local CLI/field-test capability. Bỏ GTSRB-only converter, embedded split helpers hoặc packer chỉ sau khi đã chuyển test/CLI cần giữ sang evaluator chung; nếu chưa thay được thì giữ rõ tên `training/legacy_baseline/`, không gọi là unused.
- [ ] Run toàn bộ training suite bằng synthetic data, notebook build/execute và CLI `--help`; kiểm thử shell/Colab Linux path, Windows path có dấu cách. Actual weights smoke dùng data tạm, opt-in, không tải dataset trong CI.
- [ ] Commit: `refactor(training): organize ML tools with versioned cache compatibility`.

### Task 6: Web/docs/test entry points và công cụ không còn nhiệm vụ

**Files:** `frontend/management.html/js/css`, shared scripts; `README.md`, `docs/*`, `scripts/prepare_public_repo.py`, `tests/test_public_repository.py`, `.github/workflows/ci.yml`, `tests/browser_server.py`, Playwright configs. Thêm `tests/test_repository_entrypoints.py` cho hợp đồng đường dẫn thực.

**Interfaces:** staff URL cũ và `/app/` không đổi; static redirect/alias có test nếu move asset. Web user là lab tương thích cho đến khi Flutter parity đạt.

- [ ] Test đỏ bằng HTTP/CLI thật: management HTML tải shared assets 200; guest không vào xử lý staff; deep link sign/history giữ nguyên; chạy launcher từ thư mục khác vẫn dùng canonical source. Không test bằng assertion literal trong README.
- [ ] Tách JS/CSS theo shared/staff, giữ HTML URL entry. Không đổi bundler/framework. Chỉ move `index`/`observations` sang lab sau khi 5 flow Flutter parity xanh và có redirect/alias hợp lệ; nếu chưa đủ thì giữ file cũ có ghi chú mục đích.
- [ ] Rà `prepare_public_repo.py`: exporter một lần hiện không bao phủ đầy đủ Flutter và docs mới. Đề xuất retire exporter khỏi source phát triển thường ngày; chuyển kiểm tra chống credentials/runtime/academic artifacts thành policy check read-only trên `git ls-files`, giữ toàn bộ negative fixtures bảo vệ.
- [ ] Gom docs theo getting-started/runtime/training/testing/development; một trang index chỉ lối. README bỏ hướng dẫn model 10 lớp như giới hạn duy nhất, mô tả đúng reviewed mapping. Chưa publish số liệu model thành cam kết sản phẩm.
- [ ] Chỉ nhóm tests sau khi chuyển helper import chéo `test_*` sang fixtures package; không đổi glob theo cách bỏ sót suite. Chạy Python/JS/Flutter, cả hai E2E suites, build web/APK và kiểm tra tất cả link/entry point mới.
- [ ] Commit: `refactor(repo): organize web assets and developer entry points`.

## Rollback và điều kiện dừng

- Mỗi task chỉ stage file thuộc task; revert source commit nếu regression. Không rollback bằng xoá DB, thay weights hoặc sửa catalog/manifest cho khớp.
- Cache không đọc được sau move: dừng ở facade cũ, giữ fixture lỗi và khôi phục module; không rerun audit hàng chục nghìn ảnh như giải pháp mặc định.
- Flow web chưa có Flutter tương đương: giữ web lab. CNN history không đọc được: chưa xoá schema/decoder.
- Mapping 35 lớp, sửa split/nhãn, train mới và kích hoạt model thuộc plan model riêng sau audit, không nhập chung vào refactor.

## Checklist review trước implementation

- [ ] Duyệt hướng dọn tăng dần, giữ runtime layout và URL.
- [ ] Duyệt chỉ hai notebook chính, năm notebook cũ lưu bằng Git history.
- [ ] Duyệt hoặc hoãn việc retire prediction CNN (Task 3).
- [ ] Xác nhận giữ web lab cho tới khi đủ parity, không xoá lập tức.
- [ ] Giữ thay đổi `mobile/DESIGN.md` và runtime/doc riêng của user.

Chưa có task nào ở trên được đánh dấu đã làm. Audit checkpoint là công việc riêng đã hoàn thành trong workspace, không đồng nghĩa model được nghiệm thu.


## Execution outcome

Tasks 1?6 implemented. Web user pages remain a test lab because native/physical-device parity is a separate acceptance gate. Tests remain flat while shared test helpers rely on current imports. Five notebook variants and CNN prediction writers were retired; legacy readers/CLIs remain compatible. See the linked completion report for evidence and limitations.
