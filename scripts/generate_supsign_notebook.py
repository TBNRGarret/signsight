"""Build the standalone SupSign/YOLO11s Colab notebook from tested code."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'notebooks/SignSight_SupSign_YOLO11s_Colab.ipynb'


def build_notebook():
    cells=[]
    def add(kind, source, identifier):
        cell=dict(cell_type=kind,id=identifier,metadata={},source=source.strip().splitlines(keepends=True))
        if kind=='code':cell.update(execution_count=None,outputs=[])
        cells.append(cell)
    def md(source,identifier):add('markdown',source,identifier)
    def code(source,identifier):add('code',source,identifier)
    md("""# SignSight — EDA + train SupSign 35 lớp, YOLO11s

Fine-tune **YOLO11s pretrained** trên SupSign 107 lớp, xuất taxonomy 35 lớp dành cho ô tô.
Chọn **Runtime → Change runtime type → GPU**, rồi chạy các cell theo thứ tự.

**Sửa SOURCE_ZIP và RUN_NAME ở cell Cấu hình; xem EDA rồi bật LABEL_REVIEWED để train.** Đặt ZIP SupSign lên Drive một lần.
Notebook chứa sẵn toàn bộ code chuẩn bị/train; không cần clone repo hay đăng nhập dịch vụ dataset.
Ảnh train được đọc từ SSD local Colab; dataset đã chuẩn bị và checkpoint giữ trên Drive qua các phiên.

Cả hai ZIP từng khảo sát có ảnh trùng giữa split. Notebook bỏ split nguồn, kiểm tra toàn bộ ảnh/nhãn,
loại trùng SHA-256, cách ly nhãn lỗi hoặc bản sao khác nhãn rồi chia theo nhóm.
Nếu không có group CSV, dùng dHash + block tên frame làm **heuristic phát triển**.
Điểm test lúc đó chưa chứng minh hiệu quả trên chuyến xe/địa điểm độc lập.

Nguồn API: [YOLO11](https://docs.ultralytics.com/models/yolo11/), [Train/resume](https://docs.ultralytics.com/modes/train/).
""",'intro')
    code("""import sys, subprocess, os
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['WANDB_MODE'] = 'disabled'
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
                       'ultralytics==8.4.173', 'PyYAML>=6,<7', 'tqdm>=4.66,<5'])
import torch
assert torch.cuda.is_available(), 'Bật GPU runtime trước khi train.'
print('GPU:', torch.cuda.get_device_name(0), '| Torch:', torch.__version__)
""",'install')
    md("""## 1. Cấu hình và Google Drive

Đường dẫn mặc định tương ứng: **My Drive / SignSight / datasets / archive (1).zip**.
Tên ZIP có thể khác; sửa SOURCE_ZIP cho đúng. Không dùng archive.zip 100 lớp thay vào mà giữ nhầm tên nguồn.

Mặc định: 80 epochs, ảnh 640, batch 8. Nếu hết VRAM, bắt đầu một run mới với batch 4.
Giữ 640 làm mốc trước; thử 960 trong run khác để so sánh trên cùng split.
Đổi **DATASET_VERSION** khi thay ZIP nguồn; cache cũ chỉ được tái sử dụng cho cùng phiên bản nguồn.
GROUPS_CSV tùy chọn có cột `path,group`; path là đường dẫn ảnh bên trong ZIP, ví dụ
`train/images/33292.png,trip_01`. Khi cung cấp, phải điền nhóm cho mọi ảnh hợp lệ được giữ lại, kể cả bản sao.
Nhóm cần dựa trên thông tin thu thập thật. Không tự coi tên file là metadata chuyến xe.
""",'config-guide')
    code("""from pathlib import Path
from google.colab import drive
drive.mount('/content/drive')

SOURCE_ZIP = Path('/content/drive/MyDrive/SignSight/datasets/archive (1).zip')
PERSIST = Path('/content/drive/MyDrive/SignSight/supsign_training')
WORK = Path('/content/signsight_supsign')
DATASET_VERSION = 'supsign107-car35-v3'
RUN_NAME = 'yolo11s_car35_640_v3'
GROUPS_CSV = None  # hoặc Path('/content/drive/MyDrive/SignSight/capture_groups.csv')
EPOCHS = 80
IMAGE_SIZE = 640
BATCH = 8
RESUME = False  # True để tiếp tục RUN_NAME cũ từ last.pt, với cùng cấu hình
SMOKE = False   # True chỉ thử 1 epoch; không dùng run smoke để kết luận chất lượng
LABEL_REVIEWED = False  # Sau khi xem EDA/ảnh bbox bên dưới, đổi True để bắt đầu train
RUN_HELDOUT_TEST = False  # chỉ bật sau khi chốt model/settings bằng validation
SEED = 42
FRAME_BLOCK_SIZE = 100
NEAR_HASH_DISTANCE = 4  # dHash: nhóm ứng viên ảnh gần giống, không chứng minh cùng chuyến

assert RUN_NAME and Path(RUN_NAME).name == RUN_NAME and RUN_NAME not in ('.', '..')
assert DATASET_VERSION and Path(DATASET_VERSION).name == DATASET_VERSION and DATASET_VERSION not in ('.', '..')
PERSIST.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(WORK / '.ultralytics')
CACHE_ZIP = PERSIST / 'datasets' / (DATASET_VERSION + '.zip')
DATASET_ROOT = WORK / DATASET_VERSION
RUN_DIR = PERSIST / 'runs' / (RUN_NAME + ('_smoke' if SMOKE else ''))
print('Input:', SOURCE_ZIP)
print('Cache:', CACHE_ZIP)
print('Run:', RUN_DIR)
""",'config')
    embedded={name:(ROOT/name).read_text(encoding='utf-8') for name in
              ('scripts/dataset_eda.py','scripts/supsign_training.py')}
    code("""# Code đã kiểm thử, nhúng trong notebook để chạy độc lập.
import json, shutil, csv, zipfile
TRAINING_FILES = """+repr(embedded)+"""
CODE_ROOT = WORK / 'pipeline'
for relative, source in TRAINING_FILES.items():
    target = CODE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
(CODE_ROOT / 'scripts/__init__.py').touch()
if str(CODE_ROOT) not in sys.path: sys.path.insert(0, str(CODE_ROOT))
from scripts.supsign_training import (CAR35, recipe, prepare_supsign, verify_dataset,
    digest_file, pack_dataset, restore_dataset, train_experiment, evaluate_checkpoint,
    summarize_prepared_dataset)
GROUPS = None
if GROUPS_CSV is not None:
    with Path(GROUPS_CSV).open(newline='', encoding='utf-8-sig') as stream:
        group_rows = list(csv.DictReader(stream))
    assert all(row.get('path') and row.get('group') for row in group_rows), 'CSV cần path,group.'
    GROUPS = {row['path']: row['group'] for row in group_rows}
    assert len(GROUPS) == len(group_rows), 'CSV có đường dẫn trùng.'
RECIPE = recipe(CAR35, SEED, FRAME_BLOCK_SIZE, NEAR_HASH_DISTANCE, GROUPS)
print('Taxonomy:', len(CAR35), 'lớp. Cache sẽ kiểm tra cùng recipe/code và checksum.')
""",'pipeline')
    cells[-1]['metadata']={'cellView':'form','jupyter':{'source_hidden':True}}
    md("""## 2. Chuẩn bị dataset hoặc khôi phục cache

Lần đầu đọc/hash toàn bộ ZIP có thể mất thời gian. Cần đủ ổ local cho ZIP và dataset đã lọc,
và đủ Drive để giữ cache + các run. Không giải nén ZIP nguồn tùy ý; chỉ ghi ảnh/nhãn đã kiểm tra.
Sau khi có cache trên Drive, runtime mới không cần copy hoặc audit lại ZIP thô.
Cache có checksum; thay code/classes/grouping thì phải dùng một DATASET_VERSION mới.
V3 giữ đủ lớp trong train nếu có thể tạo ba split không rỗng mà không tách nhóm.
Lớp chỉ có trong một nhóm được giữ ở train; val/test có thể thiếu lớp đó và được ghi rõ.

Nhãn lỗi bị cách ly cả ảnh, không lặng lẽ sửa annotation nguồn. Ảnh trùng byte nhưng nhãn khác
cũng bị cách ly để xem lại. Ảnh chỉ chứa lớp ngoài scope được giữ làm nền đối với 35 lớp mục tiêu.
""",'prepare-guide')
    code("""from tqdm.auto import tqdm
if DATASET_ROOT.exists():
    info = verify_dataset(DATASET_ROOT)
    manifest = json.loads((DATASET_ROOT / 'manifest.json').read_text())
    assert manifest['recipe'] == RECIPE, 'Đổi DATASET_VERSION: dataset local dùng recipe khác.'
    print('Dùng dataset local đã kiểm tra:', info['images'], 'ảnh')
elif CACHE_ZIP.is_file():
    manifest = restore_dataset(CACHE_ZIP, DATASET_ROOT, expected_recipe=RECIPE)
    print('Đã khôi phục cache Drive, không đọc lại ZIP thô.')
else:
    assert SOURCE_ZIP.is_file(), f'Không thấy ZIP: {SOURCE_ZIP}. Sửa đường dẫn ở cell Cấu hình.'
    required = SOURCE_ZIP.stat().st_size * 2.3 + 2*1024**3
    free = shutil.disk_usage(WORK).free
    assert free >= required, f'Ổ local cần khoảng {required/1024**3:.1f} GiB trống; còn {free/1024**3:.1f}.'
    local_zip = WORK / 'source_supsign.zip'
    # Copy thẳng từ Drive, không dùng upload lại qua trình duyệt.
    shutil.copy2(SOURCE_ZIP, local_zip)
    manifest = prepare_supsign(local_zip, DATASET_ROOT, classes=CAR35, groups=GROUPS,
        seed=SEED, block_size=FRAME_BLOCK_SIZE, near_threshold=NEAR_HASH_DISTANCE,
        progress=lambda items, desc, unit: tqdm(items, desc=desc, unit=unit))
    print('Đang kiểm tra và lưu cache dataset lên Drive...', flush=True)
    pack_dataset(DATASET_ROOT, CACHE_ZIP)
    local_zip.unlink()  # chỉ xóa bản sao local do cell này tạo, không xóa ZIP trên Drive
    print('Đã lưu cache Drive:', CACHE_ZIP)
from collections import Counter
split_counts = Counter(row['split'] for row in manifest['images'])
print(' | '.join(f'{s}: {split_counts[s]:,} ảnh' for s in ('train', 'val', 'test')))
print('Loại bản sao:', manifest['duplicates_removed'], '| Cách ly:', len(manifest['excluded']))
print('Split:', manifest['split_provenance'], '| Test thực địa độc lập:', manifest['independent_field_test'])
for split, missing in manifest['missing_classes'].items():
    if missing: print('Lớp thiếu ở', split, ':', ', '.join(missing))
""",'prepare')
    md("""## EDA trước khi train — lưu báo cáo trên Drive

Thống kê **đúng dataset 35 lớp sau khi lọc**, kèm audit nguồn trong `source_summary`/manifest.
Xuất JSON + CSV (ảnh, bbox, số mẫu từng lớp), biểu đồ phân bố lớp/split, kích thước ảnh,
diện tích và cạnh ngắn bbox ở kích thước train. `boxes_under_16px` giúp nhận ra biển nhỏ khó học.
Không audit lại ZIP thô nếu đã có cache. Chỉ in tóm tắt; chi tiết lỗi/cách ly nằm trong manifest.
Nhóm filename/dHash vẫn là heuristic; EDA không thay tập kiểm tra qua kính ô tô độc lập.
""", 'eda-guide')
    code("""import matplotlib.pyplot as plt
from collections import Counter
eda = summarize_prepared_dataset(DATASET_ROOT, imgsz=IMAGE_SIZE)
EDA_ROOT = PERSIST / 'eda' / DATASET_VERSION
EDA_ROOT.mkdir(parents=True, exist_ok=True)
(EDA_ROOT / 'dataset_eda.json').write_text(json.dumps(eda['summary'], ensure_ascii=False, indent=2), encoding='utf-8')
for key in ('class_counts', 'images', 'boxes'):
    rows = eda[key]
    with (EDA_ROOT / (key + '.csv')).open('w', newline='', encoding='utf-8-sig') as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
fig, axes = plt.subplots(2, 2, figsize=(18, 14))
y = list(range(len(eda['class_counts']))); starts = [0] * len(y)
for split in ('train', 'val', 'test'):
    values = [r[split] for r in eda['class_counts']]
    axes[0,0].barh(y, values, left=starts, label=split)
    starts = [a+b for a,b in zip(starts, values)]
axes[0,0].set_yticks(y, [r['name'] for r in eda['class_counts']], fontsize=8)
axes[0,0].set_title('Boxes per class / split'); axes[0,0].legend()
axes[0,1].hist([r['short_side_at_input'] for r in eda['boxes']], bins=40)
axes[0,1].axvline(16, color='red', linestyle='--'); axes[0,1].set_title(f'BBox short side at input {IMAGE_SIZE} (px)')
axes[1,0].scatter([r['width'] for r in eda['images']], [r['height'] for r in eda['images']], s=3, alpha=.15)
axes[1,0].set(xlabel='Image width', ylabel='Image height', title='Image dimensions')
axes[1,1].hist([r['area_fraction'] for r in eda['boxes']], bins=40)
axes[1,1].set_title('BBox area / image area')
fig.tight_layout(); fig.savefig(EDA_ROOT / 'eda_overview.png', dpi=150); plt.show(); plt.close(fig)
summary = eda['summary']
print(f"EDA: {summary['images']:,} images | {summary['boxes']:,} boxes | {summary['negative_images']:,} negatives")
print(f"Small boxes (<16 px at {IMAGE_SIZE}): {summary['boxes_under_16px']:,}")
print('Duplicate copies removed:', summary['duplicates_removed'], '| Quarantined:', summary['excluded_images'])
print('Saved:', EDA_ROOT)
""", 'eda')
    md("""## 3. Kiểm tra nhãn và phân bố lớp

Xem ảnh đầy đủ, bbox và tên lớp trước khi train. Phân biệt cấm ô tô/cấm chung, cấm đỗ/cấm dừng,
biển hướng trái/phải. Class ID mới là 0–34 theo CAR35; **không dùng ID này thay trực tiếp vào database 10 lớp**.
Các lớp thiếu val/test phải được ghi nhận khi đọc metric; chưa có nhãn không có nghĩa model đạt chất lượng.
""",'preview-guide')
    code("""import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
import random
sample_rows = manifest['images'].copy()
random.Random(SEED).shuffle(sample_rows)
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for axis in axes.flat: axis.axis('off')
for axis, row in zip(axes.flat, sample_rows[:6]):
    with Image.open(DATASET_ROOT / row['image']) as source: image = source.convert('RGB')
    draw = ImageDraw.Draw(image)
    for line in (DATASET_ROOT / row['label']).read_text().splitlines():
        if not line.strip(): continue
        cls, x, y, w, h = map(float, line.split())
        box = ((x-w/2)*image.width, (y-h/2)*image.height, (x+w/2)*image.width, (y+h/2)*image.height)
        draw.rectangle(box, outline='yellow', width=2)
        draw.text((max(0, box[0]), max(0, box[1]-12)), CAR35[int(cls)], fill='yellow')
    axis.imshow(image); axis.set_title(row['split'])
plt.tight_layout(); plt.show()
# Gọn 35 dòng để thấy lớp ít mẫu; không in hàng chục nghìn đường dẫn.
print(f"{'Class':35s} {'train':>7s} {'val':>7s} {'test':>7s}")
for i, name in enumerate(CAR35):
    values = [manifest['class_counts'][s].get(str(i), manifest['class_counts'][s].get(i, 0)) for s in ('train', 'val', 'test')]
    print(f'{name:35s} {values[0]:7d} {values[1]:7d} {values[2]:7d}')
""",'preview')
    md("""## 4. Train YOLO11s

Tải pretrained **yolo11s.pt**, không tiếp tục model GTSRB cũ. Tắt lật ngang/dọc và xoay ảnh để giữ nghĩa biển.
Checkpoint, results.csv, cấu hình và plots được ghi vào RUN_DIR trên Drive, còn ảnh train ở local Colab.
Best được chọn theo validation. Cell này **không đánh giá test**.

Nếu runtime ngắt giữa chừng: mở lại notebook, giữ RUN_NAME/EPOCHS/IMAGE_SIZE/BATCH,
đổi RESUME=True rồi chạy lại các cell. Checkpoint last.pt giữ trạng thái optimizer để resume;
run đã hoàn tất có thể không còn resume được. Run mới phải có tên mới.
""",'train-guide')
    code("""assert LABEL_REVIEWED, 'Xem EDA và ảnh bbox, rồi đổi LABEL_REVIEWED=True ở cell Cấu hình.'
BEST = train_experiment(DATASET_ROOT, RUN_DIR,
    epochs=1 if SMOKE else EPOCHS, imgsz=IMAGE_SIZE, batch=BATCH, device='0', resume=RESUME)
print('Best checkpoint:', BEST)
""",'train')
    md("""## 5. Validation và test có chủ đích

Chọn cấu hình bằng validation; so sánh precision/recall/mAP từng lớp, không chỉ mAP tổng.
Giữ RUN_HELDOUT_TEST=False trong lúc chọn model. Khi bật True, kết quả test vẫn ghi rõ đây là split
của dataset, chưa phải một tập thu thập thực địa độc lập. Không dùng test để điều chỉnh confidence.
Chọn EVAL_NAME mới nếu muốn lưu một lượt đánh giá khác.
""",'evaluation-guide')
    code("""EVAL_NAME = 'evaluation_v1'
validation = evaluate_checkpoint(BEST, DATASET_ROOT, RUN_DIR / EVAL_NAME / 'val',
                                 imgsz=IMAGE_SIZE, batch=BATCH)
print('Validation:', json.dumps(validation['metrics'], indent=2))
if RUN_HELDOUT_TEST:
    test_report = evaluate_checkpoint(BEST, DATASET_ROOT, RUN_DIR / EVAL_NAME / 'test',
        split='test', allow_test=True, imgsz=IMAGE_SIZE, batch=BATCH)
    print('Dataset test:', json.dumps(test_report['metrics'], indent=2))
else:
    print('Chưa chạy test. Chốt cấu hình bằng val trước khi bật RUN_HELDOUT_TEST.')
from IPython.display import display
for name in ('results.png', EVAL_NAME + '/val/confusion_matrix.png'):
    plot = RUN_DIR / name
    if plot.is_file(): display(Image.open(plot))
""",'evaluate')
    md("""## 6. Thử ảnh đường phố riêng (tùy chọn)

Upload vài ảnh qua kính xe / ảnh không có biển / biển xa để xem bbox. Đây là kiểm tra trực quan,
không thay phép đánh giá với ground truth. Confidence xem ảnh không thay metric mAP của validation.
""",'photo-guide')
    code("""TRY_OWN_PHOTOS = False
if TRY_OWN_PHOTOS:
    from google.colab import files
    from ultralytics import YOLO
    uploaded = files.upload()
    photo_root = WORK / 'own_photos'; photo_root.mkdir(exist_ok=True)
    paths = []
    for filename, content in uploaded.items():
        target = photo_root / Path(filename).name
        target.write_bytes(content); paths.append(str(target))
    for result in YOLO(str(BEST)).predict(paths, conf=0.25, imgsz=IMAGE_SIZE, save=False):
        display(Image.fromarray(result.plot()[..., ::-1]))
""",'own-photos')
    md("""## 7. Tải ZIP kết quả

ZIP gồm best.pt, last.pt, cấu hình train, metric, plots và manifest dataset; **không kèm toàn bộ ảnh dataset**.
Đã có bản trên Drive nếu trình duyệt tải chậm. Dùng files.download để tránh link localhost không tải được.

Model 35 lớp là artifact thử nghiệm. Backend SignSight hiện nhận taxonomy 10 lớp: cần nâng mapping,
validation và kiểm thử tương thích dữ liệu cũ trước khi thay checkpoint phục vụ app.
""",'export-guide')
    code("""from datetime import datetime, timezone
from google.colab import files
export_name = RUN_NAME + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
export_root = WORK / 'exports' / export_name
export_root.mkdir(parents=True, exist_ok=False)
shutil.copytree(RUN_DIR, export_root / 'run')
if 'EDA_ROOT' in globals() and EDA_ROOT.is_dir(): shutil.copytree(EDA_ROOT, export_root / 'eda')
metadata = export_root / 'dataset'; metadata.mkdir()
for name in ('data.yaml', 'manifest.json'): shutil.copy2(DATASET_ROOT / name, metadata / name)
(metadata / 'classes.json').write_text(json.dumps(CAR35, indent=2), encoding='utf-8')
archive = Path(shutil.make_archive(str(export_root), 'zip', export_root))
exports_drive = PERSIST / 'exports'; exports_drive.mkdir(exist_ok=True)
drive_export = exports_drive / archive.name
shutil.copy2(archive, drive_export)
print('Drive:', drive_export)
files.download(str(archive))
""",'export')
    return dict(cells=cells,metadata=dict(accelerator='GPU',colab=dict(name=TARGET.name),
        kernelspec=dict(display_name='Python 3',language='python',name='python3'),
        language_info=dict(name='python',version='3.11')),nbformat=4,nbformat_minor=5)


if __name__=='__main__':
    TARGET.write_text(json.dumps(build_notebook(),ensure_ascii=False,indent=1),encoding='utf-8')
    print(TARGET)
