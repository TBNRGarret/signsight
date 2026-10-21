"""Generate a standalone CPU-only Colab EDA notebook for the supplied datasets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'notebooks/SignSight_Vietnam_Dataset_EDA_Colab.ipynb'


def build_notebook():
    cells = []
    def md(text):
        cells.append({'cell_type':'markdown','metadata':{},'source':text.strip().splitlines(keepends=True)})
    def code(text):
        cells.append({'cell_type':'code','metadata':{},'source':text.strip().splitlines(keepends=True),
                      'execution_count':None,'outputs':[]})
    md('''# SignSight — EDA dataset biển báo Việt Nam trên Colab
Chạy từ trên xuống; **CPU runtime là đủ**, chưa cần tốn GPU/compute units cho train.
Hai nguồn: [supsign](https://www.kaggle.com/datasets/578dd08176b0761a7a087edb6388fa15abcf21ead5fc4c490bb77a259a6d03c9)
và [data trafficsign / vitsdb](https://www.kaggle.com/datasets/ea915509b5230ca5abf2cc50f8fc31319685c45abe0471e8aa40aba5a6c6ace9).
Metadata phiên bản 1 ghi khoảng 16 GB và 14,1 GB; chưa xác nhận cấu trúc/nhãn. API public từng trả 403.
Notebook tự tải bằng KaggleHub khi tài khoản có quyền; không yêu cầu upload ZIP từ máy tính.
Có thể đọc dataset đã tải ở `LOCAL_ROOTS`, kể cả ZIP nằm trong thư mục đó, không giải nén thêm.

EDA nhận diện YOLO detection TXT, VOC XML, COCO JSON. File chưa hỗ trợ/nhãn thiếu được báo rõ,
**không coi ảnh thiếu nhãn là ảnh nền đã xác nhận**. Không train, sửa nhãn, gộp class hay xóa ảnh trùng.
Không chạy `dataset.py` hay script bất kỳ lấy từ dataset.''')
    code('''import sys, subprocess
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'kagglehub', 'Pillow', 'PyYAML', 'pandas', 'matplotlib', 'tqdm'])
from pathlib import Path
from datetime import datetime, timezone
import json, os, shutil, importlib.util, importlib.metadata, random
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
from tqdm.auto import tqdm
from IPython.display import display
pd.set_option('display.max_colwidth', 100)
pd.set_option('display.max_rows', 25)''')
    md('''## 1. Cấu hình
Giữ `MAX_IMAGES=None` để thống kê toàn bộ ảnh/nhãn; đặt `3000` nếu muốn khảo sát nhanh trước.
`HASH_LIMIT=2000` chỉ đọc toàn bộ byte của tối đa 2.000 ảnh **mỗi dataset** để tìm trùng tuyệt đối.
Đặt `None` để hash toàn bộ (có thể lâu với ~30 GB), `0` để bỏ qua. Hash mẫu không chứng minh toàn bộ dataset sạch.
`VERIFY_DECODE=False` đọc header ảnh; bật True để thử giải mã toàn bộ mỗi ảnh và tìm thêm ảnh hỏng.

Drive miễn phí thường không đủ cho cả hai bộ: mặc định cache ở runtime, ZIP báo cáo tải về cuối notebook.
`USE_DRIVE=True` giữ thêm báo cáo trên Drive; `CACHE_DATASETS_ON_DRIVE=True` mới giữ cả dữ liệu tải về,
cần đủ dung lượng và có thể chậm do I/O Drive. KaggleHub cache giúp chạy lại không tải lại khi cache còn nguyên.
Nếu thiếu ổ đĩa, chạy một dataset mỗi lượt bằng `ACTIVE_DATASETS`.''')
    code('''ACTIVE_DATASETS = ['vitsdb', 'supsign']  # có thể dùng ['vitsdb'] trước
LOCAL_ROOTS = {}  # ví dụ {'vitsdb': '/content/drive/MyDrive/datasets/vitsdb'}; đây là THƯ MỤC
USE_DRIVE = False
CACHE_DATASETS_ON_DRIVE = False
KAGGLE_LOGIN = False  # True nếu cần đăng nhập bằng prompt; không dán API token vào code/output
MAX_IMAGES = None
ANNOTATION_FORMAT = 'auto'  # auto / yolo / voc / coco; chọn rõ nếu một ảnh có nhiều format
HASH_LIMIT = 2000
VERIFY_DECODE = False
SEED = 42
SOURCES = {
    'supsign': {'handle': 'trnghiutrng/supsign/versions/1', 'metadata_bytes': 15988455171},
    'vitsdb': {'handle': 'trnghiutrng/vitsdb/versions/1', 'metadata_bytes': 14059710820},
}
assert ACTIVE_DATASETS and len(set(ACTIVE_DATASETS)) == len(ACTIVE_DATASETS)
assert set(ACTIVE_DATASETS) <= set(SOURCES)
WORK = Path('/content/signsight_eda')
WORK.mkdir(parents=True, exist_ok=True)
if USE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
assert not CACHE_DATASETS_ON_DRIVE or USE_DRIVE, 'Bật USE_DRIVE để giữ cache trên Drive.'
PERSISTENT = Path('/content/drive/MyDrive/SignSight/eda') if USE_DRIVE else None
CACHE = PERSISTENT/'kagglehub_cache' if CACHE_DATASETS_ON_DRIVE else WORK/'kagglehub_cache'
CACHE.mkdir(parents=True, exist_ok=True)
os.environ['KAGGLEHUB_CACHE'] = str(CACHE)
OUT = WORK/('report_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
OUT.mkdir(exist_ok=False)
disk = shutil.disk_usage(CACHE)
print(f'Ổ cache còn trống: {disk.free/1e9:.1f} GB')
print(f'Tổng dung lượng metadata nguồn đã chọn: {sum(SOURCES[s]["metadata_bytes"] for s in ACTIVE_DATASETS)/1e9:.1f} GB')
print('Cần chừa thêm dung lượng tải/cache; kích thước metadata không bảo đảm kích thước ZIP/giải nén.')''')
    md('''## 2. Nạp code EDA có sẵn
Cell này chứa bản sao module đã kiểm thử từ repo; không cần clone repo trên Colab.
ZIP được đọc tại chỗ; ZIP lồng trong ZIP, RAR/7z/TAR chỉ được kiểm kê, chưa đọc nội dung.
Không đổi taxonomy 10 lớp của app trong bước EDA.''')
    code('''EDA_SOURCE = ''' + repr((ROOT/'scripts/dataset_eda.py').read_text(encoding='utf-8')) + '''
module_path = WORK/'dataset_eda.py'
module_path.write_text(EDA_SOURCE, encoding='utf-8')
spec = importlib.util.spec_from_file_location('signsight_dataset_eda', module_path)
eda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eda)
print('EDA reader sẵn sàng — không train model.')''')
    cells[-1]['metadata'] = {'cellView':'form','jupyter':{'source_hidden':True}}
    md('''## 3. Lấy dữ liệu
KaggleHub tự dùng Colab Secret `KAGGLE_API_TOKEN` nếu đã cấu hình, hoặc bật `KAGGLE_LOGIN` để nhập qua prompt.
Tài khoản cần được phép truy cập hai bộ; API token không tự cấp quyền dataset riêng.
Nếu 403, mở link thầy gửi bằng đúng tài khoản Kaggle và kiểm tra quyền với người chia sẻ.
Có thể tải bằng giao diện Kaggle rồi đặt thư mục chứa dữ liệu/ZIP vào `LOCAL_ROOTS`.
Không lặp retry hoặc dùng URL khác để vượt quyền truy cập. Nếu một bộ chưa tải được, báo cáo ghi rõ phạm vi bộ còn lại.
[Tài liệu KaggleHub](https://github.com/Kaggle/kagglehub).''')
    code('''import kagglehub
if KAGGLE_LOGIN:
    kagglehub.login()
ROOTS, SOURCE_ERRORS = {}, []
for name in ACTIVE_DATASETS:
    try:
        root = Path(LOCAL_ROOTS[name]) if name in LOCAL_ROOTS else Path(kagglehub.dataset_download(SOURCES[name]['handle']))
        if not root.is_dir():
            raise FileNotFoundError('LOCAL_ROOTS phải là thư mục có dữ liệu hoặc ZIP bên trong.')
        ROOTS[name] = root
        print(name, '→', root)
    except Exception as error:
        SOURCE_ERRORS.append({'dataset':name, 'error_type':type(error).__name__})
        print(f'{name}: chưa lấy được dữ liệu ({type(error).__name__}). Kiểm tra quyền Kaggle, ổ đĩa hoặc LOCAL_ROOTS.')
if not ROOTS:
    raise RuntimeError('Chưa có nguồn đọc được. Sửa quyền/LOCAL_ROOTS rồi chạy lại cell này; chưa chạy EDA.')''')
    md('''## 4. Kiểm kê và đọc ảnh/nhãn
Tiến trình chỉ cập nhật một thanh mỗi dataset. Bản đồ lớp giữ riêng từng dataset và namespace file nhãn;
ID `0` của hai bộ không mặc định là cùng loại biển. Nếu nhiều bản export cùng gán nhãn một ảnh,
ảnh được đánh dấu ambiguous thay vì tự chọn một bản.
COCO JSON tối đa 256 MiB/file; YAML tên lớp tối đa 1 MiB; annotation quá giới hạn được ghi vào issues.
`split=unknown` nghĩa là chưa suy ra được từ tên thư mục, không có nghĩa dataset đã được chia đúng.''')
    code('''for old_reader in globals().get('READERS', {}).values():
    old_reader.close()
READERS, RESULTS, INVENTORY = {}, {}, []
for name, root in ROOTS.items():
    reader = READERS[name] = eda.DatasetReader(root)
    for filename, (_, member, size) in reader.entries.items():
        INVENTORY.append({'dataset':name, 'path':filename, 'extension':Path(filename).suffix.lower(),
                          'storage_kind':'zip_member' if member is not None else 'filesystem', 'bytes':size})
    RESULTS[name] = eda.audit_dataset(reader, name, image_limit=MAX_IMAGES, hash_limit=HASH_LIMIT,
        seed=SEED, verify_decode=VERIFY_DECODE, progress=tqdm,
        annotation_format=globals().get('ANNOTATION_FORMAT', 'auto'))
    summary = RESULTS[name]['summary']
    print(f'{name}: {summary["images_scanned"]:,}/{summary["images_total"]:,} ảnh; '
          f'{summary["valid_boxes"]:,} box hợp lệ; {summary["issues"]:,} vấn đề; '
          f'{summary["images_hashed"]:,} ảnh đã hash')
inventory_df = pd.DataFrame(INVENTORY, columns=['dataset','path','extension','storage_kind','bytes'])
images_df = pd.DataFrame([r for result in RESULTS.values() for r in result['images']],
    columns=['dataset','path','split','parent_folder','width','height','mode','format','annotation_status','boxes','sha256'])
boxes_df = pd.DataFrame([r for result in RESULTS.values() for r in result['boxes']],
    columns=['dataset','path','split','format','label_namespace','class_id','class_name','class_mapped',
             'x_norm','y_norm','width_norm','height_norm','area_fraction','iscrowd','short_side_at_640'])
issues_df = pd.DataFrame([r for result in RESULTS.values() for r in result['issues']], columns=['dataset','path','message'])
duplicates = eda.duplicate_groups(images_df.to_dict('records'))
display(inventory_df.groupby(['dataset','storage_kind','extension']).size().rename('files').reset_index().head(30))
display(images_df.groupby(['dataset','split','annotation_status']).size().rename('images').reset_index())
if images_df.empty:
    print('Không thấy ảnh hỗ trợ. Xem inventory: có thể còn archive lồng/RAR/7z hoặc cấu trúc khác; chưa kết luận dataset rỗng.')
display(issues_df.head(20))''')
    md('''## 5. Phân bố lớp, độ phân giải, kích thước biển
Biểu đồ lớp chỉ đếm box hợp lệ đã đọc; nếu chạy sample hoặc nhiều lỗi annotation thì đây chưa phải tổng dataset.
Ảnh không có detection annotations vẫn có thể là dataset classification: xem parent_folder và inventory, không tự gán lớp từ thư mục.
`short_side_at_640` ước lượng cạnh ngắn bbox sau resize giữ tỉ lệ với cạnh dài ảnh = 640 px, trước padding;
đây không phải metric AP-small của COCO. Nhiều box rất nhỏ là lý do thử ảnh đầu vào lớn hơn trước khi chọn model xlarge.''')
    code('''class_columns = ['dataset','label_namespace','class_id','class_name']
if not boxes_df.empty:
    class_counts = boxes_df.groupby(class_columns, dropna=False).agg(instances=('path','size'), images=('path','nunique')).reset_index()
    class_counts = class_counts.sort_values(['dataset','instances'], ascending=[True,False])
else:
    class_counts = pd.DataFrame(columns=class_columns+['instances','images'])
display(class_counts.head(30))
display(images_df[['dataset','width','height']].groupby('dataset').describe() if not images_df.empty else images_df)
display(images_df.groupby(['dataset','parent_folder']).size().rename('images').sort_values(ascending=False).head(20))
fig, axes = plt.subplots(2, 2, figsize=(15, 11))
for name, group in images_df.dropna(subset=['width','height']).groupby('dataset'):
    axes[0,0].hist(group['width'], bins=30, alpha=.5, label=name)
    axes[0,1].scatter(group['width'], group['height'], s=5, alpha=.25, label=name)
axes[0,0].set(xlabel='Image width (px)', ylabel='Images', title='Resolution distribution')
axes[0,1].set(xlabel='Width (px)', ylabel='Height (px)', title='Image dimensions')
if not class_counts.empty:
    top = class_counts.nlargest(25, 'instances').copy()
    top['label'] = top['dataset']+' | '+top['class_id'].astype(str)+' | '+top['class_name']
    top.plot.barh(x='label', y='instances', ax=axes[1,0], legend=False)
    axes[1,0].invert_yaxis()
else:
    axes[1,0].text(.05,.5,'No readable detection boxes',transform=axes[1,0].transAxes)
axes[1,0].set_title('Top classes — dataset IDs kept separate')
for name, group in boxes_df.groupby('dataset'):
    axes[1,1].hist(group['short_side_at_640'], bins=40, alpha=.5, label=name)
axes[1,1].set(xlabel='Box short side after resize to 640 (px)', ylabel='Instances', title='Small-sign analysis')
for ax in [axes[0,0], axes[0,1], axes[1,1]]:
    if ax.get_legend_handles_labels()[0]: ax.legend()
fig.tight_layout()
fig.savefig(OUT/'distributions.png', dpi=150, bbox_inches='tight')
plt.show()
if not boxes_df.empty:
    small = boxes_df.assign(under_16px=boxes_df['short_side_at_640']<16,
                           under_32px=boxes_df['short_side_at_640']<32)
    display(small.groupby('dataset')[['under_16px','under_32px']].mean().mul(100).round(2).rename(columns=lambda x:x+'_percent'))
print('Nhóm ảnh giống hệt byte trong phạm vi hash:', len(duplicates))
print('Nhóm giao nhau giữa split đã nhận diện:', sum(group['cross_split'] for group in duplicates))
print('Nhóm giao nhau giữa dataset:', sum(group['cross_dataset'] for group in duplicates))
print('SHA-256 chỉ phát hiện file giống hệt; chưa phát hiện ảnh nén lại/frame gần trùng.')''')
    md('''## 6. Ảnh mẫu và bounding box
Nên xem cả ảnh nhiều box, thiếu nhãn và lỗi. Không suy diễn chất lượng dataset chỉ từ vài ảnh mẫu.
Mặc định chọn tối đa 3 ảnh mỗi dataset, ưu tiên ảnh có box; ảnh trên biểu đồ đã thu nhỏ để tránh giữ ảnh 4K trong output.''')
    code('''chosen = []
for name, group in images_df.dropna(subset=['width','height']).groupby('dataset'):
    candidates = group.sort_values('boxes', ascending=False).head(20)
    chosen += candidates.sample(n=min(3,len(candidates)), random_state=SEED).to_dict('records')
if chosen:
    fig, axes = plt.subplots(len(chosen), 1, figsize=(14, 5*len(chosen)), squeeze=False)
    for ax, row in zip(axes.flat, chosen):
        try:
            with READERS[row['dataset']].open(row['path']) as stream, Image.open(stream) as original:
                image = original.convert('RGB')
                image.thumbnail((1400,900))
            ax.imshow(image)
            selected = boxes_df[(boxes_df['dataset']==row['dataset']) & (boxes_df['path']==row['path'])]
            for box in selected.to_dict('records'):
                x,y,w,h = box['x_norm']*image.width,box['y_norm']*image.height,box['width_norm']*image.width,box['height_norm']*image.height
                ax.add_patch(patches.Rectangle((x,y),w,h,fill=False,edgecolor='lime',linewidth=2))
                ax.text(x,y,str(box['class_name']),color='black',fontsize=8,bbox={'facecolor':'lime','alpha':.8,'pad':1})
            ax.set_title(f'{row["dataset"]} | {row["annotation_status"]} | {row["path"]}',fontsize=9)
        except Exception as error:
            ax.text(.05,.5,f'Preview failed: {type(error).__name__}',transform=ax.transAxes)
        ax.axis('off')
    fig.tight_layout();fig.savefig(OUT/'samples.png',dpi=120,bbox_inches='tight');plt.show()
else:
    print('Chưa có ảnh đọc được để vẽ. Xem issues/inventory.')''')
    md('''## 7. Xuất báo cáo và tải về
ZIP chỉ gồm báo cáo CSV/JSON và hình EDA, không đóng gói lại dataset ~30 GB hay API credentials.
Giữ `summary.json`, `class_counts.csv`, `issues.csv`, `duplicate_groups.json` và hình samples để quyết định bước train.
Không ghép hai bộ theo ID số trước khi đối chiếu tên lớp/QCVN. Cần kiểm tra frame/cảnh gần trùng và giữ test độc lập theo địa điểm/video.
Khuyến nghị model phải dựa trên nhãn hợp lệ, kích thước biển, số lớp và VRAM thực tế; notebook này không tự kết luận model nào tốt nhất.''')
    code('''def export_csv(frame, name):
    # Protect spreadsheet readers while JSON keeps original class/path strings.
    safe = frame.copy()
    for column in safe.select_dtypes(include=['object','string']).columns:
        safe[column] = safe[column].map(lambda value: "'"+value if isinstance(value,str) and value.startswith(('=','+','-','@')) else value)
    safe.to_csv(OUT/name, index=False, encoding='utf-8-sig')
for filename, frame in [('inventory.csv',inventory_df),('images.csv',images_df),('boxes.csv',boxes_df),
                        ('class_counts.csv',class_counts),('issues.csv',issues_df)]:
    export_csv(frame,filename)
summary = {'created_utc':datetime.now(timezone.utc).isoformat(), 'requested_datasets':ACTIVE_DATASETS,
           'loaded_datasets':list(ROOTS), 'source_errors':SOURCE_ERRORS, 'image_limit':MAX_IMAGES,
           'hash_limit_per_dataset':HASH_LIMIT, 'seed':SEED, 'verify_decode':VERIFY_DECODE,
           'datasets':{name:result['summary'] for name,result in RESULTS.items()},
           'versions':{package:importlib.metadata.version(package) for package in ['kagglehub','Pillow','pandas','matplotlib','PyYAML']},
           'exact_duplicate_groups':len(duplicates),
           'caveats':['Missing annotation is not confirmed background.', 'Class IDs are not merged across datasets.',
                      'Exact-byte hashes do not detect re-encoded or near-duplicate images.',
                      'Charts and class counts cover scanned/readable data only.']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'class_counts.json').write_text(class_counts.to_json(orient='records',force_ascii=False,indent=2),encoding='utf-8')
(OUT/'duplicate_groups.json').write_text(json.dumps(duplicates,ensure_ascii=False,indent=2),encoding='utf-8')
archive = Path(shutil.make_archive(str(OUT),'zip',OUT))
if PERSISTENT:
    target = PERSISTENT/'reports'/archive.name
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists(), 'Không ghi đè báo cáo Drive cũ.'
    shutil.copy2(archive,target)
    print('Bản sao Drive:',target)
print('ZIP báo cáo:',archive)
from google.colab import files
files.download(str(archive))''')
    for index, cell in enumerate(cells):
        cell['id'] = f'eda-{index:02d}'
    return {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
            'language_info':{'name':'python'},'colab':{'name':TARGET.name,'provenance':[]}},'cells':cells}


if __name__ == '__main__':
    TARGET.write_text(json.dumps(build_notebook(),ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(TARGET)
