"""Generate the two active standalone CAR35 V4 Colab notebooks."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EDA_TARGET=ROOT/'notebooks/SignSight_CAR35_EDA_Colab.ipynb'
TRAIN_TARGET=ROOT/'notebooks/SignSight_CAR35_YOLO11s_Train_Colab.ipynb'


def _cell(kind,name,source):
    result=dict(cell_type=kind,id=name,metadata={},source=(source.strip()+'\n').splitlines(keepends=True))
    if kind=='code':result.update(execution_count=None,outputs=[])
    if name=='pipeline':result['metadata']=dict(cellView='form',jupyter=dict(source_hidden=True))
    return result


def _build(stage):
    handoff=json.loads(Path(__file__).with_name('car35_handoff.json').read_text(encoding='utf-8'))
    review=handoff.get('reviewed_revision',{})
    names=['training/__init__.py','training/data/__init__.py','training/experiments/__init__.py',
           'training/data/common.py','training/data/downloads.py','training/data/car35_bundle.py',
           'training/data/label_patch.py','training/data/car35_revision.py',
           'training/experiments/car35.py']
    files={n:(ROOT/n).read_text(encoding='utf-8') for n in names}
    title='EDA CAR35 — nhãn đã rà R3' if stage=='eda' else 'Train CAR35 — nhãn đã rà R3 với YOLO11s'
    cells=[_cell('markdown','intro',f'''# SignSight — {title}

Dùng ZIP **CAR35 V4 đã chia sẵn** và ZIP patch R3; không cần SupSign gốc, không chia lại train/val/test.
Mặc định tạo revision đã rà nhãn: 36.980 ảnh / 40.522 bbox. Không thêm 461 ảnh ViTSD chưa rà.
Tải dataset bằng **gdown**; không mount Drive. Notebook chạy độc lập, không clone repo.
Chọn {'CPU' if stage=='eda' else 'GPU'} runtime. Dữ liệu chỉ nằm trong `/content`; lưu notebook không lưu dataset hay checkpoint.
Split: 25.886 train / 5.547 val / 5.547 test; 35 lớp. Có ảnh cùng cảnh giữa split và lớp hiếm ít mẫu holdout.
Đây là split phát triển, chưa phải test thực địa độc lập. Không so trực tiếp mAP với V3.
'''),_cell('code','install',f'''import sys, subprocess, os
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['WANDB_MODE'] = 'disabled'
packages = ['Pillow>=10,<13', 'matplotlib>=3.8,<4', 'PyYAML>=6,<7', 'gdown==5.2.0']
{'packages.append("ultralytics==8.4.173")' if stage=='train' else ''}
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *packages])
'''),_cell('markdown','config-guide','''## 1. Cấu hình

Upload ZIP CAR35 đã được cung cấp lên Drive, chia sẻ file cho phép tải bằng link, rồi dán link vào SOURCE_URL.
Giữ nguyên hai checksum để khóa đúng dữ liệu. Runtime/tài khoản mới chỉ cần notebook và link ZIP; gdown sẽ tải lại.
APPLY_REVIEWED_PATCH=True mặc định: thêm PATCH_URL là link ZIP patch nhỏ. False dùng baseline V4.
Checksum patch và manifest revision được điền sẵn; không đổi chúng cho một file khác.
V4 được giải nén một lần vào staging rồi sửa nhãn trên bản mới; không đổi ảnh, nhóm hay split.
Runtime mới cần tải V4 và patch lại. Giữ bản V4 để so sánh; không resume run V4 với nhãn revision.
Không có DOWNLOAD=False để bỏ qua dataset ở runtime mới. Runtime cũ có dataset đã xác minh thì dùng lại.
Kết quả không tự lưu lên Drive. Tải ZIP kết quả trước khi runtime bị xóa.
'''),_cell('code','config',f'''from pathlib import Path
import sys, os
WORK = Path('/content/signsight_car35')
WORK.mkdir(parents=True, exist_ok=True)
(WORK / '.ultralytics').mkdir(exist_ok=True)
os.environ['YOLO_CONFIG_DIR'] = str(WORK / '.ultralytics')
SOURCE_URL = ''  # Dán link file ZIP CAR35 trên Drive, không phải folder
DATASET_SHA256 = {handoff['zip_sha256']!r}
EXPECTED_MANIFEST_SHA256 = {handoff['manifest_sha256']!r}
APPLY_REVIEWED_PATCH = True  # False chỉ khi cần chạy baseline V4 gốc
PATCH_URL = ''  # Link ZIP patch R3, không phải dataset ZIP
PATCH_SHA256 = {review.get('patch_sha256','')!r}
REVISED_DATASET_VERSION = {review.get('dataset_version','car35_v4_reviewed_r3_2026-11-19')!r}
EXPECTED_REVISED_MANIFEST_SHA256 = {review.get('manifest_sha256','')!r}
EXPORT_REVISED_DATASET = False  # Chỉ dùng trong EDA; True sẽ tạo thêm ZIP dataset lớn
DATASET_ROOT = WORK / 'dataset'
RUN_NAME = 'yolo11s_car35_reviewed_r3_640' if APPLY_REVIEWED_PATCH else 'yolo11s_car35_v4_640'
RUN_DIR = WORK / 'runs' / RUN_NAME
EPOCHS = 80
IMAGE_SIZE = 640
BATCH = 8
DEVICE = '0'
RESUME = False  # Chỉ True khi RUN_DIR còn last.pt và training_request.json
RUN_HELDOUT_TEST = False  # Chỉ bật sau khi chốt cấu hình bằng validation
DOWNLOAD_RESULTS = True
assert RUN_NAME and Path(RUN_NAME).name == RUN_NAME and RUN_NAME not in ('.', '..')
print('Dataset local:', DATASET_ROOT)
'''),_cell('code','pipeline',f'''# Helpers được nhúng để notebook chạy độc lập sau khi upload.
import hashlib, importlib, json, shutil
TRAINING_FILES = {files!r}
PIPELINE_ID = hashlib.sha256(json.dumps(TRAINING_FILES, sort_keys=True).encode()).hexdigest()
CODE_ROOT = WORK / 'pipeline' / PIPELINE_ID
for relative, source in TRAINING_FILES.items():
    target = CODE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
for name in list(sys.modules):
    if name in ('training', 'training.data', 'training.experiments') or name in (
        'training.data.common', 'training.data.downloads', 'training.data.car35_bundle',
        'training.data.label_patch', 'training.data.car35_revision', 'training.experiments.car35'):
        del sys.modules[name]
sys.path.insert(0, str(CODE_ROOT))
importlib.invalidate_caches()
from training.data.downloads import download_drive_zip
from training.data.car35_bundle import restore_car35_bundle, verify_car35
from training.data.car35_revision import restore_car35_revision, pack_car35_revision
from training.experiments.car35 import train_car35, evaluate_car35, export_car35_run
print('Pipeline:', PIPELINE_ID[:16])
'''),_cell('code','prepare','''expected_manifest = EXPECTED_MANIFEST_SHA256
DATASET_ROOT = WORK / 'dataset'
if APPLY_REVIEWED_PATCH:
    assert PATCH_SHA256 and EXPECTED_REVISED_MANIFEST_SHA256, 'Cần checksum patch và manifest revision đã rà.'
    assert REVISED_DATASET_VERSION and Path(REVISED_DATASET_VERSION).name == REVISED_DATASET_VERSION and REVISED_DATASET_VERSION not in ('.','..'), 'Dataset version không hợp lệ.'
    DATASET_ROOT = WORK / REVISED_DATASET_VERSION
    expected_manifest = EXPECTED_REVISED_MANIFEST_SHA256
if DATASET_ROOT.exists():
    dataset_info = verify_car35(DATASET_ROOT, expected_manifest_sha256=expected_manifest)
else:
    assert SOURCE_URL.strip(), 'Điền SOURCE_URL bằng link file ZIP CAR35 trên Drive.'
    if APPLY_REVIEWED_PATCH:
        assert PATCH_URL.strip(), 'Điền PATCH_URL bằng link ZIP patch R3 trước khi tải dataset.'
    archive = download_drive_zip(SOURCE_URL, WORK / 'downloads' / 'car35_v4.zip', expected_sha256=DATASET_SHA256)
    if APPLY_REVIEWED_PATCH:
        patch_archive = download_drive_zip(PATCH_URL, WORK / 'downloads' / ('patch_' + PATCH_SHA256[:12] + '.zip'),
            expected_sha256=PATCH_SHA256)
        print('Khôi phục V4, replay patch và kiểm tra revision; không tạo bản sao thứ hai của toàn bộ ảnh...', flush=True)
        dataset_info = restore_car35_revision(archive, patch_archive, DATASET_ROOT,
            expected_sha256=DATASET_SHA256, expected_source_manifest_sha256=EXPECTED_MANIFEST_SHA256,
            expected_patch_sha256=PATCH_SHA256, dataset_version=REVISED_DATASET_VERSION,
            expected_manifest_sha256=EXPECTED_REVISED_MANIFEST_SHA256)
    else:
        dataset_info = restore_car35_bundle(archive, DATASET_ROOT,
            expected_sha256=DATASET_SHA256, expected_manifest_sha256=EXPECTED_MANIFEST_SHA256)
manifest = json.loads((DATASET_ROOT / 'manifest.json').read_text(encoding='utf-8'))
if APPLY_REVIEWED_PATCH:
    assert manifest.get('dataset_version') == REVISED_DATASET_VERSION
    assert manifest['label_revision']['patch_archive_sha256'] == PATCH_SHA256
print('Dataset version:', dataset_info['dataset_version'], '| Manifest:', dataset_info['manifest_sha256'])
print(f"CAR35: {dataset_info['images']:,} images | {dataset_info['boxes']:,} boxes | 35 classes")
for split in ('train', 'val', 'test'):
    print(split, ':', dataset_info['split_images'][split], 'images')
print('Giữ nguyên split. Test thực địa độc lập:', dataset_info['independent_field_test'])
''')]
    if stage=='eda':
        cells.extend([_cell('markdown','eda-guide','''## 2. EDA đúng bộ CAR35 đã đóng gói

Không đọc lại SupSign gốc hay đổi split. Biểu đồ dùng số bbox đã đối soát với nhãn thực tế.
ZIP EDA chứa manifest, bảng lớp, biểu đồ và báo cáo/ảnh preview đi kèm dataset.
Với revision, summary/biểu đồ/counts mới thay cho report V4 cũ; provenance giữ manifest V4 và patch để đối chiếu.
Các report/preview V4 được giữ riêng trong dataset tại provenance/v4_reports, không trình bày như nhãn mới.
Vẫn có ảnh cùng cảnh ở nhiều split; hai lớp hết cấm chỉ có một bbox test/lớp.
EXPORT_REVISED_DATASET=True sẽ đóng gói thêm dataset lớn và checksum; mặc định False để tiết kiệm ổ đĩa.
'''),_cell('code','eda','''import csv
import matplotlib.pyplot as plt
EDA_ROOT = WORK / 'eda'; EDA_ROOT.mkdir(exist_ok=True)
rows = [dict(class_id=i, name=name, **{s:dataset_info['class_counts'][s].get(i, 0) for s in ('train','val','test')})
        for i,name in enumerate(dataset_info['names'])]
with (EDA_ROOT / 'class_counts.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
fig, ax = plt.subplots(figsize=(12, 12)); left = [0]*35
for split in ('train','val','test'):
    values = [r[split] for r in rows]
    ax.barh(range(35), values, left=left, label=split)
    left = [a+b for a,b in zip(left,values)]
ax.set_yticks(range(35), dataset_info['names'], fontsize=8); ax.legend(); ax.set_title(dataset_info['dataset_version'] + ' boxes by split')
fig.tight_layout(); fig.savefig(EDA_ROOT / 'class_distribution.png', dpi=150); plt.close(fig)
(EDA_ROOT / 'summary.json').write_text(json.dumps(dataset_info, ensure_ascii=False, indent=2), encoding='utf-8')
for name in ('manifest.json','data.yaml','report.html','dataset_report.json','README.md'):
    if (DATASET_ROOT / name).is_file(): shutil.copy2(DATASET_ROOT / name, EDA_ROOT / name)
if (DATASET_ROOT / 'previews').is_dir(): shutil.copytree(DATASET_ROOT / 'previews', EDA_ROOT / 'previews', dirs_exist_ok=True)
for name in ('v4_manifest.json','label_patch.json'):
    source = DATASET_ROOT / 'provenance' / name
    if source.is_file():
        (EDA_ROOT / 'provenance').mkdir(exist_ok=True)
        shutil.copy2(source, EDA_ROOT / 'provenance' / name)
print('EDA saved:', EDA_ROOT)
'''),_cell('code','export','''from datetime import datetime, timezone
name = 'car35_v4_eda_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
if EXPORT_REVISED_DATASET:
    PREPARED_ZIP = WORK / (dataset_info['dataset_version'] + '_prepared_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.zip')
    prepared_handoff = pack_car35_revision(DATASET_ROOT, PREPARED_ZIP)
    (EDA_ROOT / 'prepared_handoff.json').write_text(json.dumps(prepared_handoff, ensure_ascii=False, indent=2), encoding='utf-8')
RESULT_ZIP = Path(shutil.make_archive(str(WORK / name), 'zip', EDA_ROOT))
print('EDA ZIP:', RESULT_ZIP)
if DOWNLOAD_RESULTS:
    from google.colab import files
    files.download(str(RESULT_ZIP))
    if EXPORT_REVISED_DATASET:
        files.download(str(PREPARED_ZIP))
        files.download(str(PREPARED_ZIP.with_suffix(PREPARED_ZIP.suffix + '.sha256')))
''')])
    else:
        cells.extend([_cell('markdown','train-guide','''## 2. Train YOLO11s

Bắt đầu từ pretrained `yolo11s.pt`, vì model SupSign cũ có thể đã thấy các ảnh nay thuộc holdout V4.
Chọn GPU runtime trước khi chạy. Nếu hết VRAM, giảm BATCH ở lần chạy mới; resume phải giữ đúng settings cũ.
Checkpoint best/last và mỗi 5 epoch chỉ lưu local. Khi dừng giữa chừng, chạy cell Xuất kết quả nếu đã có weights.
RESUME chỉ dùng khi run còn trong runtime hoặc đã tự tải/khôi phục run đầy đủ; notebook không tự phục hồi checkpoint từ tài khoản khác.
'''),_cell('code','train','''if DEVICE != 'cpu':
    import torch
    assert torch.cuda.is_available(), 'Chọn Runtime → Change runtime type → GPU trước khi train.'
try:
    best_checkpoint = train_car35(DATASET_ROOT, RUN_DIR, epochs=EPOCHS, imgsz=IMAGE_SIZE,
        batch=BATCH, device=DEVICE, resume=RESUME)
    print('Best:', best_checkpoint)
except KeyboardInterrupt:
    print('Đã dừng. Chạy cell Xuất kết quả để giữ checkpoint nếu run đã tạo weights.')
'''),_cell('markdown','evaluate-guide','''## 3. Validation và test riêng

Validation được dùng để xem lỗi/chọn cấu hình. Test mặc định tắt; chỉ bật khi đã chốt.
Đủ 35 tên lớp không có nghĩa đủ mẫu kiểm thử. Giữ báo cáo giới hạn scene overlap và lớp hiếm khi đọc metric.
'''),_cell('code','evaluate','''from datetime import datetime, timezone
def fresh_evaluation_directory(label):
    output = RUN_DIR / label
    if output.exists():
        output = RUN_DIR / (label + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    return output
checkpoint = RUN_DIR / 'weights' / 'best.pt'
if checkpoint.is_file():
    val_report = evaluate_car35(checkpoint, DATASET_ROOT, fresh_evaluation_directory('validation'),
        imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE)
    print('Validation:', val_report['metrics'])
    if RUN_HELDOUT_TEST:
        test_report = evaluate_car35(checkpoint, DATASET_ROOT, fresh_evaluation_directory('test'), split='test', allow_test=True,
            imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE)
        print('Development test:', test_report['metrics'])
else:
    print('Chưa có best.pt để evaluate; có thể xuất last.pt nếu đã train một phần.')
'''),_cell('markdown','export-guide','''## 4. Xuất kết quả về máy

ZIP gồm best.pt/last.pt, checkpoint định kỳ, plots/results.csv, training_request, evaluation reports và manifest/checksum.
Tải ZIP trước khi đóng runtime. Sau khi bạn gửi kết quả, mới rà chất lượng và mapping để tích hợp; notebook không đổi model đang phục vụ.
'''),_cell('code','export','''from datetime import datetime, timezone
name = RUN_NAME + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RESULT_ZIP = export_car35_run(RUN_DIR, DATASET_ROOT, WORK / (name + '.zip'))
print('Training result:', RESULT_ZIP)
if DOWNLOAD_RESULTS:
    from google.colab import files
    files.download(str(RESULT_ZIP))
''')])
    return dict(cells=cells,metadata=dict(colab=dict(name=(EDA_TARGET if stage=='eda' else TRAIN_TARGET).name),
        kernelspec=dict(display_name='Python 3',language='python',name='python3'),language_info=dict(name='python',version='3.11')),
        nbformat=4,nbformat_minor=5)


def build_car35_eda_notebook():return _build('eda')
def build_car35_train_notebook():return _build('train')


def main():
    for path,builder in ((EDA_TARGET,build_car35_eda_notebook),(TRAIN_TARGET,build_car35_train_notebook)):
        path.write_text(json.dumps(builder(),ensure_ascii=False,indent=1),encoding='utf-8');print(path)

if __name__=='__main__':main()
