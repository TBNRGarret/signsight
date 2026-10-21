"""Build a self-contained Colab/Kaggle notebook from tested pipeline sources."""
import base64
import gzip
import io
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_notebook():
    cells = []
    def md(source): cells.append({'cell_type':'markdown','metadata':{},'source':source.strip().splitlines(keepends=True)})
    def code(source): cells.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':source.strip().splitlines(keepends=True)})
    md('''# SignSight — YOLO trên Colab / Kaggle
Chọn **Runtime → Change runtime type → GPU (T4)** trên Colab, hoặc bật GPU + Internet trên Kaggle.
Notebook chứa code, taxonomy và các CSV train/val/test hiện tại. Không cần clone repo hoặc upload ZIP.
Dùng cùng nguồn GTSRB như notebook CNN: ưu tiên dataset đã gắn ở `/kaggle/input`, nếu thiếu thì tải bằng KaggleHub.
Bật `USE_DRIVE = True` trên Colab để lưu dataset YOLO đã chuẩn bị và checkpoint qua các phiên runtime.
GTSRB ROI là baseline kỹ thuật; cần dữ liệu cảnh đường phố Việt Nam để đánh giá triển khai.
Checkpoint và metric detection độc lập với CNN best_model.pth / accuracy 99,47%.''')
    code('''import sys, subprocess
subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'ultralytics==8.4.173', 'PyYAML>=6,<7', 'kagglehub'])
import torch
assert torch.cuda.is_available(), 'Chọn GPU runtime trước khi train.'
print(torch.__version__, torch.cuda.get_device_name(0))''')
    embedded = {name:(ROOT/name).read_text(encoding='utf-8') for name in (
        'ai_engine/config.py', 'ai_engine/detection.py', 'ai_engine/prepare_detection_data.py',
        'ai_engine/train_detection.py', 'ai_engine/notebook_data.py', 'data/taxonomy.json')}
    splits = {name:(ROOT/'data/processed'/name).read_bytes() for name in ('train.csv','val.csv','test.csv')}
    # GzipFile writes OS=255 on every platform. Python 3.11 gzip.compress
    # with mtime=0 delegates the header to zlib, exposing the build OS.
    payload = {}
    for name, data in splits.items():
        buffer = io.BytesIO()
        with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, compresslevel=9, mtime=0) as archive:
            archive.write(data)
        payload[name] = base64.b64encode(buffer.getvalue()).decode()
    checksums = {name:hashlib.sha256(data).hexdigest() for name,data in splits.items()}
    md('''## Code và splits có sẵn
Giữ nguyên split theo track và taxonomy 10 lớp của repo, không chia lại dữ liệu khi mở notebook.
Cache được định danh theo nguồn, CSV, code converter/validator và taxonomy; thay đổi đầu vào sẽ tạo cache mới.''')
    code('''#@title Khôi phục pipeline và splits có sẵn (không cần sửa dữ liệu nhúng)
from pathlib import Path
import json, os, shutil
IS_KAGGLE = Path('/kaggle/input').is_dir()
WORK = Path('/kaggle/working/signsight_yolo' if IS_KAGGLE else '/content/signsight_yolo')
WORK.mkdir(parents=True, exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(WORK / '.cache/ultralytics')
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['KAGGLEHUB_CACHE'] = str(WORK / '.cache/kagglehub')
TRAINING_FILES = ''' + repr(embedded) + '''
SPLIT_PAYLOAD = ''' + repr(payload) + '''
SPLIT_CHECKSUMS = ''' + repr(checksums) + '''
for relative, source in TRAINING_FILES.items():
    target = WORK / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
(WORK / 'ai_engine/__init__.py').touch()
sys.path.insert(0, str(WORK))
os.chdir(WORK)
from ai_engine.notebook_data import DatasetCacheMiss, prepare_cached_dataset, resolve_archive, restore_splits
from ai_engine.train_detection import validate_dataset
CSV_ROOT = restore_splits(SPLIT_PAYLOAD, SPLIT_CHECKSUMS, WORK / 'data/processed')
print('Pipeline ready:', WORK)''')
    cells[-1]['metadata'] = {'cellView': 'form', 'jupyter': {'source_hidden': True}}
    md('''## Nguồn dữ liệu và cache
`USE_DRIVE = False`: tải tự động, cache trong runtime; runtime mới có thể phải tải lại.
`USE_DRIVE = True` (khuyên dùng trên Colab): mount Drive, lần đầu lưu một ZIP đã chuẩn bị + checksum;
những phiên sau khôi phục ZIP vào ổ local để train nhanh, không tải raw dataset hay chạy converter lại.
Kaggle: Add Input → GTSRB nếu muốn dùng input có sẵn; Save Version để giữ outputs, `/kaggle/working` không tự giữ qua phiên mới.
Public dataset thường tải được không cần token; nếu Kaggle yêu cầu consent/login, làm theo thông báo KaggleHub.
`RAW_DATASET_DIR` chỉ cần đặt khi có archive riêng. Giữ nguyên `SOURCE_ID` cho nguồn mặc định;
khi đổi nguồn/custom archive, đặt ID phiên bản riêng để tránh dùng nhầm cache.''')
    code('''USE_DRIVE = False  # đổi True để giữ dataset/checkpoint trên Google Drive qua các phiên Colab
SOURCE_ID = 'meowmeowmeowmeowmeow/gtsrb-german-traffic-sign/versions/1'
RAW_DATASET_DIR = None  # ví dụ '/kaggle/input/gtsrb-german-traffic-sign'
PERSISTENT_CACHE = None
RUNS_ROOT = WORK / 'runs/detection'
if USE_DRIVE:
    assert not IS_KAGGLE, 'Google Drive mount dành cho Colab.'
    from google.colab import drive
    drive.mount('/content/drive')
    DRIVE_ROOT = Path('/content/drive/MyDrive/SignSight')
    PERSISTENT_CACHE = DRIVE_ROOT / 'yolo_datasets'
    RUNS_ROOT = DRIVE_ROOT / 'runs/detection'
RUNS_ROOT.mkdir(parents=True, exist_ok=True)''')
    code('''CACHE_ROOT = WORK / '.cache/yolo'
try:
    PORTABLE_DATA, DATASET_REPORT = prepare_cached_dataset(
        None, CSV_ROOT, CACHE_ROOT, source_id=SOURCE_ID, persistent_root=PERSISTENT_CACHE)
    print('Reused prepared dataset cache')
except DatasetCacheMiss:
    import kagglehub
    roots = [Path(RAW_DATASET_DIR)] if RAW_DATASET_DIR else [Path('/kaggle/input'), WORK / 'archive']
    if RAW_DATASET_DIR:
        assert Path(RAW_DATASET_DIR).is_dir(), 'RAW_DATASET_DIR không tồn tại.'
        def download_raw(_): raise ValueError('RAW_DATASET_DIR thiếu Train.csv/Test.csv')
    else:
        download_raw = kagglehub.dataset_download
    archive_root = resolve_archive(roots, SOURCE_ID, download_raw)
    PORTABLE_DATA, DATASET_REPORT = prepare_cached_dataset(
        archive_root, CSV_ROOT, CACHE_ROOT, source_id=SOURCE_ID, persistent_root=PERSISTENT_CACHE)
DATASET_ROOT = PORTABLE_DATA.parent
# Ultralytics resolves relative path via its datasets_dir; supply an absolute runtime path.
# Keep cached data.yaml portable so a new Colab runtime has the same fingerprint.
import yaml
config = yaml.safe_load(PORTABLE_DATA.read_text(encoding='utf-8'))
config['path'] = str(DATASET_ROOT.resolve())
DATA = WORK / 'data_runtime.yaml'
DATA.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
REPORT_PATH = WORK / 'dataset_report.json'
REPORT_PATH.write_text(json.dumps(DATASET_REPORT, indent=2, ensure_ascii=False), encoding='utf-8')
print(' | '.join(
    f"{split}: {counts['images']:,} images / {counts['instances']:,} boxes"
    for split, counts in DATASET_REPORT['splits'].items()))
print('Full validation report: dataset_report.json')''')
    md('''## Kiểm tra nhãn trước khi train
Hiển thị annotation mẫu; kiểm tra class và ROI trước khi dùng GPU.
Không dùng test để chọn model/threshold. Deduplication giữ test > val > train và ghi các bản sao bị loại vào manifest.''')
    code('''import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from ai_engine.prepare_detection_data import NAMES
fig, axes = plt.subplots(2, 3, figsize=(12, 7))
for axis, source in zip(axes.flat, sorted((DATASET_ROOT/'images/train').glob('*'))[:6]):
    image = Image.open(source).convert('RGB')
    draw = ImageDraw.Draw(image)
    label = DATASET_ROOT/'labels/train'/source.with_suffix('.txt').name
    for line in label.read_text().splitlines():
        if not line.strip(): continue
        cls, x, y, w, h = map(float, line.split())
        box = ((x-w/2)*image.width, (y-h/2)*image.height, (x+w/2)*image.width, (y+h/2)*image.height)
        draw.rectangle(box, outline='yellow', width=2)
        draw.text((box[0], box[1]), NAMES[int(cls)], fill='yellow')
    axis.imshow(image); axis.axis('off')
plt.tight_layout()''')
    md('''## Train + đánh giá val/test
Mặc định fine-tune YOLO11n COCO trên taxonomy 10 lớp, 50 epochs. Nếu GPU thiếu bộ nhớ giảm BATCH.
RUN_DIR nên nằm trên Drive khi train lâu; checkpoint tự lưu ở mỗi epoch.
Pipeline tắt flip ngang/dọc vì biển chỉ hướng; ghi seed, hashes, phiên bản, precision/recall/mAP theo lớp.
Run đã có bị từ chối để giữ kết quả trước. Test chỉ đánh giá sau khi chọn best theo val.''')
    code('''EPOCHS = 50
IMAGE_SIZE = 640
BATCH = 8
from datetime import datetime, timezone
RUN_DIR = RUNS_ROOT / datetime.now(timezone.utc).strftime('yolo_%Y%m%dT%H%M%S%fZ')  # có thể đổi sang Drive
SMOKE = False  # True cho thử pipeline 1 epoch; không dùng checkpoint smoke để triển khai
args = [sys.executable, '-m', 'ai_engine.train_detection', 'train', '--data', str(DATA),
        '--model', 'yolo11n.pt', '--allow-download', '--epochs', str(1 if SMOKE else EPOCHS),
        '--imgsz', str(IMAGE_SIZE), '--batch', str(BATCH), '--device', '0', '--workers', '2',
        '--output', str(RUN_DIR)]
if SMOKE: args.append('--smoke')
subprocess.check_call(args)
report = json.loads((RUN_DIR/'detection_report.json').read_text())
print(json.dumps(report['metrics'], indent=2, ensure_ascii=False))''')
    md('''## Xem lỗi detection
Các bảng metric và confusion matrix nằm trong thư mục run. Thử cả ảnh nền, 0/1/nhiều biển và biển ngoài scope; đây là kiểm tra riêng ngoài benchmark ROI.''')
    code('''from IPython.display import display
for split in ('val', 'test'):
    plot = RUN_DIR / f'evaluate_{split}/confusion_matrix.png'
    if plot.is_file(): display(Image.open(plot))
from ultralytics import YOLO
best = YOLO(str(RUN_DIR/'weights/best.pt'))
samples = sorted((DATASET_ROOT/'images/test').glob('*'))[:4]
for result in best.predict([str(path) for path in samples], conf=0.25, save=False):
    display(Image.fromarray(result.plot()[..., ::-1]))''')
    md('''## Tải kết quả về local
ZIP gồm best.pt, last.pt, detection_report.json, results.csv, config train, plots và data.yaml/manifest.
Giải nén, đặt best.pt vào ai_engine/checkpoints/detection/best.pt; cài requirements-yolo.txt trên server rồi restart.
Giữ detection_report.json cùng checkpoint. Chưa kết luận chất lượng cảnh đường phố nếu train bằng GTSRB ROI.''')
    code('''EXPORT = WORK / (RUN_DIR.name + '_result')
assert not EXPORT.exists(), 'Export tồn tại; chọn tên khác để giữ bản trước.'
shutil.copytree(RUN_DIR, EXPORT/'run')
(EXPORT/'dataset').mkdir()
shutil.copy2(PORTABLE_DATA, EXPORT/'dataset/data.yaml')
manifest = DATASET_ROOT/'manifest.json'
if manifest.is_file(): shutil.copy2(manifest, EXPORT/'dataset/manifest.json')
archive = shutil.make_archive(str(EXPORT), 'zip', EXPORT)
if IS_KAGGLE:
    from IPython.display import FileLink
    display(FileLink(archive))
else:
    from google.colab import files
    files.download(archive)''')
    for index,cell in enumerate(cells): cell['id']=f'signsight-{index:02d}'
    return {'cells':cells,'metadata':{'accelerator':'GPU','colab':{'name':'SignSight_YOLO_Colab.ipynb'},
             'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':5}


if __name__=='__main__':
    target=ROOT/'notebooks/SignSight_YOLO_Colab.ipynb'
    target.write_text(json.dumps(build_notebook(),ensure_ascii=False,indent=1),encoding='utf-8')
    print(target)
