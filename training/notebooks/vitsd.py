"""Generate the standalone Drive-mounted ViTSD ZIP cleaning-review notebook."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / 'notebooks/SignSight_ViTSD_Cleaning_Review_Colab.ipynb'


def _cell(kind, name, source):
    cell = dict(cell_type=kind, id=name, metadata={}, source=(source.strip()+'\n').splitlines(keepends=True))
    if kind == 'code':
        cell.update(execution_count=None, outputs=[])
    if name == 'pipeline':
        cell['metadata'] = dict(cellView='form', jupyter=dict(source_hidden=True))
    return cell


def build_notebook():
    names = ['training/__init__.py', 'training/data/__init__.py', 'training/data/common.py',
             'training/data/audit.py', 'training/data/vitsd_review.py']
    files = {name: (ROOT/name).read_text(encoding='utf-8') for name in names}
    cells = [
        _cell('markdown', 'intro', '''# SignSight — ViTSD ZIP: audit và kế hoạch làm sạch CAR35

Chọn **CPU runtime**. Notebook mount Drive của bạn, không dùng Kaggle/gdown, không cần GPU hay YOLO.
Bạn chỉ cần sửa `DRIVE_ZIP_PATH` thành đường dẫn file ZIP đang có trên Drive.

Mặc định chép ZIP **một lần** sang `/content`, đọc ảnh/nhãn trực tiếp trong ZIP, không giải nén toàn bộ.
File gốc trên Drive được giữ nguyên. Có thanh tiến độ copy/audit/dHash và cache audit trong cùng runtime.
Lưu notebook không giữ `/content`; báo cáo ZIP được lưu vào Drive và có thể tải về máy.

**Đầu ra là báo cáo trước train**: lỗi nhãn, ảnh trùng, ứng viên gần trùng, bảng mapping CAR35 và ảnh minh họa.
Chưa tự sửa nhãn, xoá ảnh, chia lại train/val/test hoặc train. Mapping tên giống nhau vẫn phải duyệt bằng mắt.
'''),
        _cell('code', 'install', '''import sys, subprocess
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'Pillow>=10,<13', 'PyYAML>=6,<7', 'tqdm>=4.66,<5', 'matplotlib>=3.8,<4'])
print('Dùng CPU runtime; không cần cài Torch/Ultralytics.')
'''),
        _cell('code', 'mount', '''from google.colab import drive
drive.mount('/content/drive')
'''),
        _cell('markdown', 'config-guide', '''## 1. Chọn file ZIP trên Drive

Trong thanh Files bên trái Colab: mở `drive/MyDrive`, tìm file ZIP → menu ba chấm → **Copy path**,
rồi dán vào `DRIVE_ZIP_PATH`. Ví dụ `/content/drive/MyDrive/datasets/ViTSD.zip`.
Không dán link chia sẻ vào biến đường dẫn. Việc mount cần bạn xác nhận truy cập tài khoản Google.

Giữ `MAX_IMAGES=None` để audit toàn bộ. Có thể dùng 200 để thử đường dẫn trước; báo cáo sẽ ghi rõ partial.
`ANNOTATION_FORMAT='yolo'` đọc TXT, bỏ COCO cùng nguồn để không đếm đôi. Chọn `'coco'` nếu cần khảo sát bản JSON riêng.
`NEAR_HASH_DISTANCE=4` thêm bước đọc lại ảnh ZIP local để tìm liên kết dHash; có thể đặt `None` để bỏ bước này.

Tham chiếu CAR35 là **tuỳ chọn**: `REFERENCE_MANIFEST_PATH` nhận `manifest.json` V4 đã lưu trên Drive
hoặc ZIP có đúng một manifest. Chỉ cần manifest, không cần upload lại ảnh CAR35.
Nếu bỏ trống, notebook vẫn chạy; báo cáo ghi **chưa kiểm tra trùng xuyên nguồn**. Tham chiếu hash không kiểm tra cảnh gần giống xuyên nguồn.
'''),
        _cell('code', 'config', '''from pathlib import Path
import sys, json, shutil, hashlib
from datetime import datetime, timezone
WORK = Path('/content/signsight_vitsd_review')
WORK.mkdir(parents=True, exist_ok=True)
DRIVE_ZIP_PATH = ''  # Ví dụ /content/drive/MyDrive/datasets/ViTSD.zip
REFERENCE_MANIFEST_PATH = ''  # Tuỳ chọn: manifest.json CAR35 V4 hoặc ZIP chứa manifest
COPY_ZIP_TO_LOCAL = True
ANNOTATION_FORMAT = 'yolo'
MAX_IMAGES = None  # Toàn bộ; dùng 200 chỉ để smoke test, không phải full audit
NEAR_HASH_DISTANCE = 4  # None: bỏ dHash; không tự thay đổi split
SAVE_REPORT_TO_DRIVE = True
DRIVE_REPORT_DIR = Path('/content/drive/MyDrive/SignSight_Reports')
DOWNLOAD_REPORT = True
print('Workspace:', WORK)
print(f'Local free: {shutil.disk_usage(WORK).free/1024**3:.1f} GiB')
'''),
        _cell('code', 'pipeline', f'''# Helpers được nhúng để notebook upload chạy độc lập, không clone repo.
import importlib, sys, hashlib, json
TRAINING_FILES = {files!r}
PIPELINE_ID = hashlib.sha256(json.dumps(TRAINING_FILES, sort_keys=True).encode()).hexdigest()
CODE_ROOT = WORK / 'pipeline' / PIPELINE_ID
for relative, source in TRAINING_FILES.items():
    target = CODE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
# Tránh dùng helper cũ còn trong bộ nhớ nếu upload notebook mới cùng runtime.
for name in list(sys.modules):
    if name == 'training' or name.startswith('training.'):
        del sys.modules[name]
sys.path.insert(0, str(CODE_ROOT))
importlib.invalidate_caches()
from training.data.vitsd_review import (copy_zip_to_local, audit_zip, load_reference,
    build_review, write_review)
print('Pipeline:', PIPELINE_ID[:16])
'''),
        _cell('markdown', 'source-guide', '''## 2. Chép ZIP một lần về ổ Colab

Copy local tránh hàng chục nghìn lượt đọc nhỏ qua Drive mount. Cần chỗ cho ZIP + khoảng trống làm báo cáo,
không cần thêm một bản toàn bộ dataset giải nén. Runtime mới phải copy lại.
Chạy lại cùng runtime sẽ kiểm tra checksum bản local trước khi dùng lại.
'''),
        _cell('code', 'source', '''from tqdm.auto import tqdm
assert DRIVE_ZIP_PATH.strip(), 'Điền DRIVE_ZIP_PATH bằng Copy path của file ZIP trong Drive.'
mounted_zip = Path(DRIVE_ZIP_PATH).expanduser()
assert mounted_zip.is_file(), f'Không thấy ZIP: {mounted_zip}; kiểm tra mount và Copy path.'
assert mounted_zip.suffix.lower() == '.zip', 'Chọn file ZIP, không phải folder.'
if COPY_ZIP_TO_LOCAL:
    # Mỗi đường dẫn nguồn có thư mục local riêng; receipt kiểm tra size/mtime và checksum.
    source_id = hashlib.sha256(str(mounted_zip.resolve()).encode()).hexdigest()[:16]
    with tqdm(total=mounted_zip.stat().st_size, unit='B', unit_scale=True, desc='Copy ZIP Drive → local') as bar:
        def copied(total):
            bar.update(total-bar.n)
        SOURCE_ZIP = copy_zip_to_local(mounted_zip, WORK/'downloads'/source_id/'dataset.zip', progress=copied)
        bar.update(bar.total-bar.n)
else:
    SOURCE_ZIP = mounted_zip
    print('Đọc trực tiếp qua mount có thể chậm. COPY_ZIP_TO_LOCAL=True được khuyến nghị.')
print('Đọc ZIP:', SOURCE_ZIP)
'''),
        _cell('markdown', 'audit-guide', '''## 3. Audit ảnh/nhãn và đề xuất mapping

Lượt đầu hash ZIP rồi decode/hash từng ảnh, có thể mất nhiều phút. Thanh tiến độ hiện sau bước hash ZIP.
Không tắt cell chỉ vì chưa có GPU usage: bước này dùng CPU/ổ đĩa.
Cache audit có fingerprint nguồn + code + cấu hình; chạy lại cùng runtime không cần audit lại ảnh nếu khớp.
Ảnh thiếu nhãn, bbox lỗi, ảnh hỏng và duplicate có annotation mâu thuẫn được liệt kê để cách ly.
Không tự coi ảnh thiếu nhãn là ảnh nền, không tự sửa bbox về biên ảnh.
'''),
        _cell('code', 'audit', '''assert 'audit_zip' in globals(), 'Chạy cell pipeline trước.'
print('Đang hash ZIP / kiểm tra cache audit...', flush=True)
audit = audit_zip(SOURCE_ZIP, annotation_format=ANNOTATION_FORMAT, image_limit=MAX_IMAGES,
    cache_dir=WORK/'audit_cache', progress=lambda items, desc, unit: tqdm(items, desc=desc, unit=unit))
reference = load_reference(REFERENCE_MANIFEST_PATH.strip() or None)
review = build_review(audit, reference=reference)
summary = review['summary']
print(f"Audit: {audit['summary']['images_scanned']:,}/{audit['summary']['images_total']:,} ảnh | {len(audit['boxes']):,} bbox có hình học hợp lệ")
print('Partial scan:', audit['summary']['partial_scan'])
print('Trạng thái nhãn:', audit['summary']['annotation_status'])
print('Nhóm trùng byte:', summary['duplicate_groups'], '| Nhóm nhãn mâu thuẫn:', summary['conflicting_duplicate_groups'])
print('Đề xuất xử lý:', summary['decisions'])
print('Đối chiếu CAR35 exact:', summary['reference_exact_check'], '| Ảnh trùng:', summary['reference_overlap_images'])
print('Chưa tạo dataset train; mapping chưa duyệt.')
'''),
        _cell('markdown', 'review-guide', '''## 4. Báo cáo có ảnh để duyệt

Xuất mọi dòng CSV; màn hình chỉ in tóm tắt. Ảnh minh họa tối đa 6 ảnh/lớp CAR35 và một số ca cách ly/cặp gần trùng.
dHash tái đọc ảnh và tạo một **forest liên kết ứng viên**, không phải mọi cặp giống nhau; không tự gom/chia dataset train.
Nhóm lớn cần rà bằng mắt trước khi chốt. Kết quả có đầy đủ đường dẫn để tìm lại ảnh/nhãn gốc trong ZIP.
`class_counts.csv` đếm bbox nguồn hợp lệ về hình học, có thể gồm box trong ảnh có lỗi khác; không phải số mẫu sạch sau loại trùng.
'''),
        _cell('code', 'review', '''RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
REPORT_ROOT = WORK/'reports'/('vitsd_car35_review_'+RUN_ID)
report_summary = write_review(SOURCE_ZIP, audit, review, REPORT_ROOT,
    near_threshold=NEAR_HASH_DISTANCE,
    progress=lambda items, desc, unit: tqdm(items, desc=desc, unit=unit))
print('Báo cáo:', REPORT_ROOT)
print('dHash:', report_summary['near_duplicates'])
print('Tải ZIP cuối notebook rồi giải nén, mở index.html để xem ảnh và liên kết CSV.')
'''),
        _cell('code', 'plots', '''import matplotlib.pyplot as plt
from collections import Counter
from training.data.common import CAR35
counts = Counter(b['class_name'] for b in audit['boxes'] if b['class_mapped'])
fig, axes = plt.subplots(1, 2, figsize=(17, 10))
axes[0].barh(range(35), [counts[n] for n in CAR35])
axes[0].set_yticks(range(35), CAR35, fontsize=8)
axes[0].set_title('CAR35 source boxes (before cleaning/dedup)')
axes[1].hist([b['short_side_at_640'] for b in audit['boxes']], bins=45)
axes[1].axvline(16, color='red', linestyle='--')
axes[1].set(xlabel='BBox short side at input 640 (px)', title='Source box sizes')
fig.tight_layout(); fig.savefig(REPORT_ROOT/'distributions.png', dpi=140)
plt.show(); plt.close(fig)
'''),
        _cell('markdown', 'export-guide', '''## 5. Lưu báo cáo — không chép ZIP dataset lên Drive lần nữa

Chỉ lưu ZIP **báo cáo nhỏ** vào `MyDrive/SignSight_Reports` và tải về máy nếu bật.
Gửi ZIP báo cáo này để rà mapping, nhãn mâu thuẫn và overlap trước khi tạo dataset V5.
Không dùng ZIP báo cáo làm dataset train. File gốc và split cũ được giữ nguyên.
Nếu runtime bị ngắt, cache local mất; Drive chỉ giữ các báo cáo đã xuất thành công.
'''),
        _cell('code', 'export', '''from google.colab import files
RESULT_ZIP = Path(shutil.make_archive(str(WORK/REPORT_ROOT.name), 'zip', REPORT_ROOT))
print(f'Report: {RESULT_ZIP.name} ({RESULT_ZIP.stat().st_size/1024**2:.1f} MiB)')
if SAVE_REPORT_TO_DRIVE:
    DRIVE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    destination = DRIVE_REPORT_DIR/RESULT_ZIP.name
    with RESULT_ZIP.open('rb') as incoming, destination.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    print('Đã lưu báo cáo trên Drive:', destination)
if DOWNLOAD_REPORT:
    files.download(str(RESULT_ZIP))
'''),
    ]
    return dict(cells=cells, metadata=dict(colab=dict(name=TARGET.name),
                kernelspec=dict(display_name='Python 3', language='python', name='python3'),
                language_info=dict(name='python', version='3.11')), nbformat=4, nbformat_minor=5)


def main():
    TARGET.write_text(json.dumps(build_notebook(), ensure_ascii=False, indent=1), encoding='utf-8')
    print(TARGET)


if __name__ == '__main__':
    main()
