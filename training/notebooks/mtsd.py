"""Build a small standalone CPU notebook for MTSD acquisition/annotation review."""
import json
from training.notebooks.car35 import ROOT, _cell

TARGET = ROOT / 'notebooks/SignSight_MTSD_Inspect_Colab.ipynb'


def build_mtsd_notebook():
    sources = {name: (ROOT / name).read_text(encoding='utf-8') for name in (
        'training/__init__.py', 'training/data/__init__.py', 'training/data/mtsd.py', 'training/data/downloads.py')}
    cells = [_cell('markdown', 'intro', '''# SignSight — MTSD: kiểm tra annotation trước

Chạy CPU. Lấy bộ **fully annotated** từ https://www.mapillary.com/dataset/trafficsign
(trang hiện yêu cầu đăng nhập). Trước mắt chỉ cần ZIP annotation có annotations/*.json và splits/train.txt.
Đây là MTSD, không phải Mapillary Vistas hoặc dữ liệu điểm biển từ Mapillary API.
Chưa cần tải mọi ZIP ảnh lớn. Không mount Drive; dùng gdown với file bạn chia sẻ, hoặc ZIP đã có trong runtime.

Notebook xuất thống kê nhãn và danh sách ảnh train ứng viên cho biển tốc độ 40/50/60/70/80.
Tên nhãn chỉ là gợi ý mapping: phải xem ảnh để xác nhận hình dạng/đơn vị và mọi biển CAR35 khác.
Không train chỉ 5 lớp thay model 35 lớp, không tự coi reviewed=yes và không thay checkpoint trong app.
'''), _cell('code', 'install', '''import sys, subprocess
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'gdown==5.2.0'])
'''), _cell('code', 'config', '''from pathlib import Path
WORK = Path('/content/signsight_mtsd')
WORK.mkdir(parents=True, exist_ok=True)
ANNOTATIONS_URL = ''  # Link gdown ZIP annotation fully annotated bạn đã tải từ MTSD
LOCAL_ANNOTATIONS_ZIP = ''  # Hoặc đường dẫn ZIP đã có trong runtime
ANNOTATIONS_SHA256 = ''  # Tùy chọn; không dùng SHA của CAR35/SupSign
'''), _cell('code', 'pipeline', f'''import sys, json, hashlib, csv, shutil
SOURCES = {sources!r}
CODE_ROOT = WORK / 'pipeline'
for relative, source in SOURCES.items():
    target = CODE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding='utf-8')
if str(CODE_ROOT) not in sys.path: sys.path.insert(0, str(CODE_ROOT))
from training.data.downloads import download_drive_zip
from training.data.mtsd import inspect_mtsd
'''), _cell('code', 'inspect', '''if LOCAL_ANNOTATIONS_ZIP.strip():
    source = Path(LOCAL_ANNOTATIONS_ZIP)
else:
    source = download_drive_zip(ANNOTATIONS_URL, WORK / 'annotations.zip', expected_sha256=ANNOTATIONS_SHA256)
with source.open('rb') as stream:
    actual_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
if ANNOTATIONS_SHA256.strip():
    assert actual_sha == ANNOTATIONS_SHA256.strip().lower(), 'Annotation ZIP checksum khác.'
report = inspect_mtsd(source)
report['source_zip_sha256'] = actual_sha
print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
print('Schema:', report['schema_example'])
print('Mapping ứng viên:', report['mapping_candidates'])
'''), _cell('code', 'export', '''from datetime import datetime, timezone
output = WORK / ('mtsd_inspect_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
output.mkdir()
(output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
for key in ('class_counts', 'mapping_candidates', 'train_candidates'):
    rows = report[key]
    if rows:
        with (output / (key + '.csv')).open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
result = shutil.make_archive(str(output), 'zip', output)
print('Gửi ZIP báo cáo này trước khi tải/ghép ảnh:', result)
from google.colab import files
files.download(result)
'''), _cell('markdown', 'next', '''## Sau khi đọc báo cáo

Lấy đúng các image archive train theo bộ MTSD được cấp. Bước sau mới chọn khoảng 500–1.500 ảnh
(mục tiêu pilot, phụ thuộc dữ liệu thực), xem ảnh/mapping, đổi toàn bộ nhãn phù hợp sang ID CAR35 0–34,
loại ảnh trùng/gần trùng với tất cả split Việt Nam. Giữ nguyên val/test Việt Nam và các nhóm cảnh liên quan.
Ảnh MTSD val/test không được lấy làm train trong pilot này.

Ghép với dữ liệu train Việt Nam hiện có, fine-tune từ checkpoint đã chốt rồi so cùng baseline trên cùng validation
và ảnh Việt Nam riêng. Không coi mAP MTSD là chất lượng chạy tại Việt Nam. /content mất khi runtime bị xóa.
''')]
    return dict(cells=cells, metadata=dict(colab=dict(name=TARGET.name),
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python', version='3.11')), nbformat=4, nbformat_minor=5)


if __name__ == '__main__':
    TARGET.write_text(json.dumps(build_mtsd_notebook(), ensure_ascii=False, indent=1), encoding='utf-8')
    print(TARGET)
