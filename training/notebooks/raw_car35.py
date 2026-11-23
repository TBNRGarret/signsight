"""Standalone raw-107 ZIP -> CAR35 preparation, EDA and YOLO11s training."""
import json
from pathlib import Path

from training.notebooks.car35 import ROOT, _cell, build_car35_eda_notebook, build_car35_train_notebook

TARGET = ROOT/'notebooks/SignSight_Raw107_CAR35_YOLO11s_Colab.ipynb'


def build_raw_car35_notebook():
    notebook = build_car35_train_notebook()
    base = {c['id']:c for c in notebook['cells']}
    modules = [
        'training/__init__.py', 'training/compatibility.py', 'training/data/__init__.py',
        'training/experiments/__init__.py', 'training/data/common.py', 'training/data/audit.py',
        'training/data/cache.py', 'training/data/downloads.py', 'training/data/supsign.py',
        'training/data/folder_dataset.py', 'training/data/folder_splits.py', 'training/data/raw_car35.py',
        'training/data/car35_bundle.py', 'training/data/car35_revision.py', 'training/data/label_patch.py',
        'training/experiments/car35.py', 'training/experiments/train.py', 'training/experiments/evaluate.py',
    ]
    files = {name:(ROOT/name).read_text(encoding='utf-8') for name in modules}
    install = ''.join(base['install']['source']).replace("'gdown==5.2.0'", "'gdown==5.2.0', 'tqdm>=4.66,<5'")
    cells = [_cell('markdown','intro','''# SignSight — ZIP 107 lớp → CAR35 → train YOLO11s

Dùng ZIP SupSign/YOLO **107 lớp**, có data.yaml và train/valid/test ở thư mục gốc.
Chỉ cần một link gdown; không mount Drive, không clone repo, không cần upload dataset mới.
Notebook tự kiểm tra ảnh/nhãn, lọc và remap 35 lớp CAR35, loại bản trùng byte,
gom ảnh gần trùng bằng dHash rồi chia nhóm theo mục tiêu 70/15/15.
Ảnh chỉ chứa lớp ngoài CAR35 được giữ làm nền đối với subset.

Đây là **dataset/split mới**, không phải V4/R3 cũ và không tự áp patch R3 khóa theo manifest cũ.
Không so trực tiếp mAP giữa hai split. dHash không chứng minh độc lập chuyến xe/thực địa.
Xem EDA và nhãn mẫu trước khi chạy cell train. Notebook không đổi model trong app.
'''), _cell('code','install',install), _cell('markdown','config-guide','''## 1. Cấu hình

Dán link file ZIP 107 lớp vào SOURCE_URL. Không điền checksum của ZIP V4 vào đây.
RAW_ZIP_SHA256 có thể để trống khi chưa có hash đáng tin cậy; hash thực tế luôn được ghi nhận.
LOCAL_SOURCE_ZIP dùng nếu ZIP raw vẫn còn trong runtime: điền đường dẫn file để khỏi tải lại.
Nếu helper cũ đã xóa file khi báo lỗi SHA, cần tải lại bằng gdown một lần.

Mọi file nằm trong /content; không tự lưu lên Drive. Cần đủ ổ cho ZIP, raw giải nén và CAR35.
Thư mục raw tạm do cell tạo sẽ được dọn sau khi chuẩn bị; ZIP gốc được giữ nguyên.
Đổi DATASET_VERSION khi đổi dữ liệu/seed/grouping/code; cache cũ không bị ghi đè.
'''), _cell('code','config','''from pathlib import Path
import sys, os
WORK = Path('/content/signsight_raw107')
WORK.mkdir(parents=True, exist_ok=True)
(WORK / '.ultralytics').mkdir(exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(WORK / '.ultralytics')
SOURCE_URL = ''  # Link file ZIP 107 lớp trên Drive
LOCAL_SOURCE_ZIP = ''  # Tùy chọn: đường dẫn ZIP raw đã có trong runtime
RAW_ZIP_SHA256 = ''  # Tùy chọn; không dùng SHA của CAR35 V4
DATASET_VERSION = 'car35_raw107_v1'
DATASET_ROOT = WORK / DATASET_VERSION
SEED = 42
NEAR_HASH_DISTANCE = 4
WORKERS = 4
RUN_NAME = 'yolo11s_' + DATASET_VERSION + '_640'
RUN_DIR = WORK / 'runs' / RUN_NAME
EPOCHS = 30
IMAGE_SIZE = 640
BATCH = 8
DEVICE = '0'
RESUME = False
RUN_HELDOUT_TEST = False
DOWNLOAD_RESULTS = True
assert DATASET_VERSION and Path(DATASET_VERSION).name == DATASET_VERSION and DATASET_VERSION not in ('.','..')
assert RUN_NAME and Path(RUN_NAME).name == RUN_NAME and RUN_NAME not in ('.','..')
print('Dataset:', DATASET_ROOT)
'''), _cell('code','pipeline',f'''# Helpers đã nhúng; chạy lại cell này để thay module cũ trong cùng runtime.
import hashlib, importlib, json, shutil
TRAINING_FILES = {files!r}
PIPELINE_ID = hashlib.sha256(json.dumps(TRAINING_FILES, sort_keys=True).encode()).hexdigest()
CODE_ROOT = WORK / 'pipeline' / PIPELINE_ID
for relative, source in TRAINING_FILES.items():
    target = CODE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
for name in list(sys.modules):
    if name in ('training','training.compatibility') or name.startswith(('training.data','training.experiments')):
        del sys.modules[name]
sys.path.insert(0, str(CODE_ROOT))
importlib.invalidate_caches()
from training.data.common import CAR35
from training.data.downloads import download_drive_zip, drive_file_id
from training.data.raw_car35 import prepare_raw_car35_zip, verify_raw_car35
from training.experiments.car35 import train_car35, evaluate_car35, export_car35_run
print('Pipeline raw107:', PIPELINE_ID[:16])
'''), _cell('markdown','prepare-guide','''## 2. Chuẩn bị CAR35 từ ZIP raw 107 lớp

Lần đầu cần tải/giải nén, decode/hash ảnh, đọc nhãn và gom gần trùng nên có thể lâu.
Có thanh tiến độ từng giai đoạn; không in hàng chục nghìn đường dẫn.
Tên số thứ tự không được dùng làm capture group. Nhóm gần trùng nằm trong cùng split.
Tỷ lệ thực tế có thể khác 70/15/15 do kích thước nhóm; lớp hiếm thiếu holdout sẽ được báo.
Dataset đã xác minh trong cùng runtime được dùng lại; không tải/audit lại raw ZIP.
'''), _cell('code','prepare','''from tqdm.auto import tqdm
progress = lambda items, desc, unit: tqdm(items, desc=desc, unit=unit)
if DATASET_ROOT.exists():
    print('Đang kiểm tra hash của CAR35 local...', flush=True)
    dataset_info = verify_raw_car35(DATASET_ROOT, dataset_version=DATASET_VERSION, seed=SEED,
        near_threshold=NEAR_HASH_DISTANCE, expected_source_sha256=RAW_ZIP_SHA256)
    print('Dùng CAR35 local đã kiểm tra; không tải/audit lại raw ZIP.')
else:
    if LOCAL_SOURCE_ZIP.strip():
        archive = Path(LOCAL_SOURCE_ZIP).expanduser()
        assert archive.is_file(), 'Không thấy LOCAL_SOURCE_ZIP; kiểm tra file còn trong runtime không.'
    else:
        assert SOURCE_URL.strip(), 'Điền SOURCE_URL bằng link ZIP 107 lớp.'
        archive = download_drive_zip(SOURCE_URL, WORK / 'downloads' / ('raw107_' + drive_file_id(SOURCE_URL) + '.zip'),
            expected_sha256=RAW_ZIP_SHA256)
    print('Kiểm tra ZIP và chuẩn bị dataset mới; không dùng hash/patch V4...', flush=True)
    dataset_info = prepare_raw_car35_zip(archive, DATASET_ROOT, dataset_version=DATASET_VERSION,
        seed=SEED, near_threshold=NEAR_HASH_DISTANCE, expected_source_sha256=RAW_ZIP_SHA256,
        workers=WORKERS, progress=progress)
manifest = json.loads((DATASET_ROOT / 'manifest.json').read_text(encoding='utf-8'))
receipt = dict(source_mode='raw107', archive_sha256=manifest['raw_zip_preparation']['source_zip_sha256'],
    dataset_version=DATASET_VERSION, manifest_sha256=dataset_info['manifest_sha256'])
(WORK / 'source_archive_verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(f"CAR35: {dataset_info['images']:,} images | {dataset_info['boxes']:,} boxes | 35 classes")
for split in ('train','val','test'):
    print(split, ':', dataset_info['split_images'][split], 'images |', dataset_info['split_groups'][split], 'groups')
for split, names in manifest['missing_classes'].items():
    if names: print('Lớp thiếu ở', split, ':', ', '.join(names))
print('Manifest:', dataset_info['manifest_sha256'])
print('Test thực địa độc lập:', dataset_info['independent_field_test'])
'''), _cell('markdown','eda-guide','''## 3. EDA và kiểm tra nhãn trước khi train

Thống kê đúng CAR35 mới chuẩn bị, không coi đủ 35 tên lớp là đủ chất lượng từng lớp.
Rà phân bố train/val/test và nhãn mẫu; giữ manifest cùng kết quả để đối chiếu benchmark.
''')]
    eda = next(c for c in build_car35_eda_notebook()['cells'] if c['id']=='eda')
    cells.append(eda)
    cells.append(_cell('code','preview','''import random
from PIL import Image, ImageDraw
sample = manifest['images'].copy(); random.Random(SEED).shuffle(sample)
fig, axes = plt.subplots(2, 3, figsize=(15, 9))
for axis in axes.flat: axis.axis('off')
for axis, row in zip(axes.flat, sample[:6]):
    with Image.open(DATASET_ROOT / row['image']) as source: image = source.convert('RGB')
    draw = ImageDraw.Draw(image)
    for line in (DATASET_ROOT / row['label']).read_text().splitlines():
        if not line.strip(): continue
        cls, x, y, w, h = map(float, line.split())
        box = ((x-w/2)*image.width, (y-h/2)*image.height, (x+w/2)*image.width, (y+h/2)*image.height)
        draw.rectangle(box, outline='yellow', width=2)
        draw.text((max(0,box[0]),max(0,box[1]-12)), CAR35[int(cls)], fill='yellow')
    axis.imshow(image); axis.set_title(row['split'])
fig.tight_layout(); fig.savefig(EDA_ROOT / 'bbox_preview.png', dpi=150); plt.show(); plt.close(fig)
'''))
    cells.append(_cell('markdown','train-guide','''## 4. Train YOLO11s

Bắt đầu từ pretrained yolo11s.pt; mặc định 640px, batch 8, 30 epoch và early stopping.
Nếu hết VRAM, giảm batch ở run mới. Resume yêu cầu cùng dataset/settings và last.pt còn trong runtime.
Best/last và checkpoint mỗi 5 epoch vẫn là file local; tải ZIP kết quả trước khi runtime bị xóa.
'''))
    cells.extend([base['train'], base['evaluate-guide'], base['evaluate'], base['export-guide']])
    export = ''.join(base['export']['source']).replace(
        "RESULT_ZIP = export_car35_run", "if RUN_DIR.is_dir() and (WORK / 'eda').is_dir():\n    shutil.copytree(WORK / 'eda', RUN_DIR / 'eda', dirs_exist_ok=True)\nRESULT_ZIP = export_car35_run")
    cells.append(_cell('code','export',export))
    notebook['cells'] = cells
    notebook['metadata']['colab']['name'] = TARGET.name
    return notebook


def main():
    TARGET.write_text(json.dumps(build_raw_car35_notebook(), ensure_ascii=False, indent=1), encoding='utf-8')
    print(TARGET)


if __name__ == '__main__': main()
