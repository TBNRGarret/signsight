"""Generate a standalone Colab EDA notebook for the user's Google Drive ZIP."""
import json
from pathlib import Path

from scripts.generate_eda_notebook import build_notebook as build_base

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'notebooks/SignSight_Drive_Dataset_EDA_Colab.ipynb'
FILE_ID = 'YOUR_DRIVE_FILE_ID'


def build_notebook():
    notebook = build_base()
    cells = notebook['cells']

    def replace(index, value):
        cells[index]['source'] = value.strip().splitlines(keepends=True)

    replace(0, f'''# SignSight — EDA dataset từ Google Drive
Nguồn đã gắn sẵn: [archive.zip](https://drive.google.com/file/d/{FILE_ID}/view).
**Chọn CPU runtime**, chạy các cell từ trên xuống. Không cần Kaggle API key hoặc clone repo.
Notebook không train model, không thay nhãn, không xóa dữ liệu và không giải nén ZIP.

EDA gồm cấu trúc file/split, kích thước ảnh, YOLO/VOC/COCO annotations, class imbalance,
box nhỏ, nhãn lỗi/thiếu và ảnh trùng byte trong phạm vi hash; có ảnh mẫu kèm bounding box.
Chưa biết số lớp/format thực tế của ZIP; ảnh không có annotation không tự trở thành background.''')
    install = ''.join(cells[1]['source']).replace("'kagglehub'", "'gdown==5.2.0'")
    replace(1, install)
    replace(2, '''## 1. Cấu hình nguồn và phạm vi EDA
Mặc định `SOURCE_MODE='download'`: tải đúng file ID đã gắn sẵn qua gdown, giữ cache ở runtime.
Lần chạy lại cùng runtime dùng cache, không tải lại. Session Colab mới mất cache runtime.

**Đọc file gốc đang có trên Drive mà không tải một bản vào runtime:** đổi thành
`SOURCE_MODE='drive'`, điền đúng `DRIVE_ARCHIVE`, rồi cấp quyền Drive mount.
Đường dẫn mặc định giả sử `archive.zip` nằm ở gốc MyDrive; sửa nếu bạn để ở folder khác.
Chỉ đọc file ZIP được chỉ định, không quét toàn bộ MyDrive. Nếu link cần đăng nhập hoặc bị quota,
dùng chế độ này; không cần đổi file thành public.

`MAX_IMAGES=3000` là khảo sát nhanh, chưa phải thống kê toàn bộ. Sau khi kiểm tra cấu trúc,
đặt `MAX_IMAGES=None` để đọc mọi ảnh/nhãn. `HASH_LIMIT=1000` hash tối đa 1.000 ảnh đã chọn;
`None` hash toàn bộ ảnh trong phạm vi scan, `0` bỏ qua. `VERIFY_DECODE=True` kiểm tra giải mã ảnh đầy đủ.
`SAVE_REPORTS_TO_DRIVE=True` mount Drive để giữ thêm báo cáo nhỏ; không sao chép dataset lên Drive.
Không đặt cache/output bên trong thư mục dữ liệu được giải nén rồi scan lẫn báo cáo.''')
    cells[2]['source'] += ['\n\nViTSD có cả YOLO TXT và COCO JSON cho cùng ảnh. Notebook chọn rõ '
                           "`ANNOTATION_FORMAT='yolo'`; đổi thành `'coco'` nếu muốn khảo sát bản COCO. "
                           "Chế độ `'auto'` vẫn báo ambiguous khi có nhiều nguồn, không tự gộp hoặc ưu tiên ngầm.\n"]
    replace(3, f'''FILE_ID = {FILE_ID!r}
SOURCE_MODE = 'download'  # 'download' hoặc 'drive'
DRIVE_ARCHIVE = '/content/drive/MyDrive/archive.zip'  # sửa nếu chọn SOURCE_MODE='drive'
SAVE_REPORTS_TO_DRIVE = False
MAX_IMAGES = 3000
ANNOTATION_FORMAT = 'yolo'  # ViTSD có cả YOLO và COCO; không dùng auto cho bản export này
HASH_LIMIT = 1000
VERIFY_DECODE = False
SEED = 42
assert SOURCE_MODE in ('download', 'drive')
assert ANNOTATION_FORMAT in ('auto', 'yolo', 'voc', 'coco')
assert MAX_IMAGES is None or (isinstance(MAX_IMAGES, int) and MAX_IMAGES > 0)
assert HASH_LIMIT is None or (isinstance(HASH_LIMIT, int) and HASH_LIMIT >= 0)
WORK = Path('/content/signsight_drive_eda')
WORK.mkdir(parents=True, exist_ok=True)
if SOURCE_MODE == 'drive' or SAVE_REPORTS_TO_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
PERSISTENT = Path('/content/drive/MyDrive/SignSight/eda') if SAVE_REPORTS_TO_DRIVE else None
CACHE = WORK/'datasets'
CACHE.mkdir(parents=True, exist_ok=True)
OUT = WORK/('report_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
OUT.mkdir(exist_ok=False)
ACTIVE_DATASETS = ['drive_dataset']
SOURCE_ERRORS = []
print(f'Ổ runtime còn trống: {{shutil.disk_usage(CACHE).free/1e9:.1f}} GB')
print('Chế độ:', SOURCE_MODE, '| Scan:', MAX_IMAGES or 'toàn bộ', '| Hash:', HASH_LIMIT)
print('Không giải nén ZIP. Nếu download, vẫn cần đủ chỗ chứa file ZIP ở runtime.')''')
    helper = ''.join(cells[5]['source'])
    helper += '\n\nDRIVE_SOURCE = ' + repr((ROOT / 'scripts/drive_eda_source.py').read_text(encoding='utf-8')) + '''
source_path = WORK/'drive_eda_source.py'
source_path.write_text(DRIVE_SOURCE, encoding='utf-8')
source_spec = importlib.util.spec_from_file_location('signsight_drive_source', source_path)
drive_source = importlib.util.module_from_spec(source_spec)
source_spec.loader.exec_module(drive_source)
'''
    replace(5, helper)
    replace(6, '''## 3. Mở ZIP nguồn
Chế độ download chỉ dùng quyền chia sẻ công khai của file; không đọc cookie trình duyệt hoặc API key.
Nếu không tải được vì quyền/quota, notebook dừng với hướng dẫn Drive mount.
Kiểm tra cấu trúc ZIP trước khi đưa vào cache chính thức; không nhận HTML đăng nhập thành dataset.
Cache được giữ theo file ID; nếu bạn thay nội dung file Drive cùng ID, dùng một thư mục `CACHE` mới.
ZIP lồng/RAR/7z chỉ được kiểm kê, chưa đọc ảnh bên trong. Không thực thi code trong dataset.
Tải file lớn có thể mất thời gian; thanh tiến trình download khác thanh tiến trình EDA.''')
    replace(7, '''archive_path = drive_source.resolve_archive(FILE_ID, CACHE,
    local_archive=DRIVE_ARCHIVE if SOURCE_MODE == 'drive' else None)
ROOTS = {'drive_dataset': archive_path}
with zipfile.ZipFile(archive_path) as archive:
    entries = archive.infolist()
    print('ZIP:', archive_path.name, f'| {archive_path.stat().st_size/1e9:.2f} GB')
    print(f'{len(entries):,} entries; tổng byte giải nén theo metadata: {sum(e.file_size for e in entries)/1e9:.2f} GB')
    print('Chỉ đọc ZIP tại chỗ; không giải nén các entries này.')''')
    # ZIP metadata comes from stdlib; no additional package or credentials.
    replace(1, ''.join(cells[1]['source']).replace('import json, os, shutil,', 'import json, zipfile, os, shutil,'))
    replace(14, '''## 7. Xuất báo cáo và tải về
ZIP báo cáo gồm inventory/images/boxes/class_counts/issues CSV, JSON tổng hợp,
duplicate_groups và các hình phân bố/preview. Không đóng gói lại dataset hoặc credentials.
`summary.json` ghi file ID, chế độ đọc, phạm vi sample/hash và phiên bản thư viện.
Nếu chưa thấy annotation được hỗ trợ, hãy gửi inventory/issues để xác định adapter cần bổ sung.
Không kết luận dataset sạch hoặc đủ để train từ sample, và chưa kết luận chất lượng model ở bước EDA.''')
    export = ''.join(cells[15]['source']).replace("'kagglehub'", "'gdown'")
    export = export.replace("'requested_datasets':ACTIVE_DATASETS,", "'requested_drive_file_id':FILE_ID, 'source_file_id':FILE_ID if SOURCE_MODE == 'download' else None, 'source_mode':SOURCE_MODE, 'source_path':str(archive_path), 'requested_datasets':ACTIVE_DATASETS,")
    replace(15, export)
    for index, cell in enumerate(cells):
        cell['id'] = f'drive-eda-{index:02d}'
    notebook['metadata']['colab']['name'] = TARGET.name
    return notebook


if __name__ == '__main__':
    TARGET.write_text(json.dumps(build_notebook(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(TARGET)
