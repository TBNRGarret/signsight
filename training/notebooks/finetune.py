"""Generate a standalone review-first raw107 CAR35 fine-tune notebook."""
import json

from training.notebooks.car35 import ROOT, _cell
from training.notebooks.raw_car35 import build_raw_car35_notebook

TARGET=ROOT/'notebooks/SignSight_CAR35_FineTune_Colab.ipynb'


def build_finetune_notebook():
    notebook=build_raw_car35_notebook();base={c['id']:c for c in notebook['cells']}
    config=''.join(base['config']['source'])+'''
# Lượt 1: review (CPU). Lượt 2: train (GPU), sau khi kiểm tra nhãn và upload review ZIP.
MODE = 'train'  # Đã review: train. Chọn review chỉ khi cần xuất gói rà nhãn mới.
RAW_ZIP_SHA256 = '80e6bdde83a543c42143dd2cfdaf6075e2706b307759346e20f859126ab0f9cf'
EXPECTED_BASE_MANIFEST_SHA256 = 'c197bb18dd27a0517ee7522803ac7f061aad7f0388abe60012c672a9378cce05'
REVIEW_URL = ''  # ZIP đã kiểm tra + reviewed=yes; nhãn đúng được giữ nguyên, tải bằng gdown
LOCAL_REVIEW_ZIP = ''  # Hoặc file ZIP đã có trong runtime
REVIEW_SHA256 = ''  # Tùy chọn checksum review ZIP, khác checksum raw/checkpoint
CHECKPOINT_URL = ''  # ZIP kết quả raw107 hoặc ZIP chứa run/weights/best.pt
LOCAL_CHECKPOINT = ''  # Hoặc đường dẫn best.pt đã có trong runtime
CHECKPOINT_MEMBER = 'run/weights/best.pt'
CHECKPOINT_SHA256 = '0d1f9b2feb2711189aa59b90db1d32c4f436940ab3ec98412c58ffe4289e4ea1'
REVIEW_PER_CLASS = 15
FINE_ROOT = WORK / 'car35_reviewed_finetune_v1'
RUN_NAME = 'yolo11s_car35_finetune_pilot_v2_640'
EPOCHS = 15
LEARNING_RATE = 0.0003
MOSAIC = 0.1
PATIENCE = 5
REGRESSION_URL = ''  # Tùy chọn: ZIP ảnh lỗi/thử thực tế, tải bằng gdown
RUN_DIR = WORK / 'runs' / RUN_NAME
BASELINE_DIR = WORK / 'evaluations' / (RUN_NAME + '_baseline')
RUN_HELDOUT_TEST = False
assert MODE in ('review','train'), 'MODE phải là review hoặc train'
'''
    install='''import sys, subprocess, os
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['WANDB_MODE'] = 'disabled'
packages = ['Pillow>=10,<13', 'matplotlib>=3.8,<4', 'PyYAML>=6,<7', 'gdown==5.2.0', 'tqdm>=4.66,<5']
if MODE == 'train': packages.append('ultralytics==8.4.173')
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *packages])
if MODE == 'train' and 'ultralytics' in sys.modules:
    assert sys.modules['ultralytics'].__version__ == '8.4.173', 'Restart runtime để bỏ module Ultralytics cũ, rồi chạy lại.'
'''
    modules=('training/data/finetune.py','training/experiments/finetune.py','training/experiments/photo_probe.py')
    extras={name:(ROOT/name).read_text(encoding='utf-8') for name in modules}
    pipeline=''.join(base['pipeline']['source']).replace('PIPELINE_ID =',f'TRAINING_FILES.update({extras!r})\nPIPELINE_ID =',1)
    pipeline+='''from training.data.finetune import create_review_pack, prepare_finetune_dataset
from training.data.common import digest_file
from training.experiments.finetune import finetune_car35, restore_initial_checkpoint
'''
    prepare=''.join(base['prepare']['source'])+'''
if EXPECTED_BASE_MANIFEST_SHA256:
    assert dataset_info['manifest_sha256'] == EXPECTED_BASE_MANIFEST_SHA256, 'Baseline manifest khác run raw107 đã rà; không áp review nhầm split.'
'''
    cells=[_cell('markdown','intro','''# SignSight — rà nhãn → fine-tune CAR35 → đối chiếu baseline

Model khởi đầu là best.pt raw107 đã train 30 epoch. Không train lại từ yolo11s.pt.
Mặc định MODE='train' cho CSV đã review; điền SOURCE_URL, REVIEW_URL và CHECKPOINT_URL rồi chạy.
**Lượt 1:** MODE='review', CPU runtime, điền SOURCE_URL của ZIP raw107. Xuất gói ảnh train để sửa nhãn.
**Lượt 2:** MODE='train', GPU runtime, điền thêm REVIEW_URL và CHECKPOINT_URL (hoặc file local).
Không mount Drive, không clone repo; mọi file trong /content sẽ mất khi runtime bị xóa.
Không tự thay model trong app. Nhãn đã review và giữ nguyên vẫn được fine-tune.

Giữ nguyên CAR35/class ID và split test. Dataset fine-tune là bản sao riêng, cần thêm dung lượng ổ đĩa.
Nếu dataset fine-tune đã có trong cùng runtime và khớp baseline/review, notebook kiểm tra rồi dùng lại.
Kết quả là benchmark phát triển, không chứng minh độ chính xác độc lập ngoài thực địa.
'''),_cell('code','config',config),_cell('code','install',install),_cell('code','pipeline',pipeline),
        base['prepare-guide'],_cell('code','prepare',prepare),
        _cell('markdown','review-guide','''## 1. Xuất ảnh để rà nhãn trước

MODE='review' chọn tối đa REVIEW_PER_CLASS ảnh train cho mỗi lớp ưu tiên: tốc độ, người đi bộ,
đường dành cho ô tô, cấm ô tô quay đầu/rẽ phải. Mẫu trải theo hash, chưa phải xếp hạng active learning.
Gói chứa ảnh nguyên cảnh, nhãn YOLO, classes.txt, review.csv và review.json khóa theo manifest baseline.
Sửa bbox/nhãn bằng công cụ annotation bạn dùng; đánh dấu reviewed=yes cho những dòng đã kiểm tra.
Không thay pixel của ảnh cũ. Không coi nhãn rỗng là nền nếu chưa rà mọi biển thuộc CAR35 trong ảnh.

Muốn thêm ảnh chụp mới: thêm images/tên.jpg + labels/tên.txt, thêm dòng review.csv với split=train hoặc val,
group là mã cảnh/chuyến xe thực tế và reviewed=yes. Cùng biển vật lý/chuyến xe phải ở cùng split.
Không thêm ảnh test vào train; không tự chuyển ảnh cũ sang split khác. Không dùng ảnh validation để sửa train.
Nén các file ở gốc ZIP hoặc trong một thư mục bọc rồi upload để lấy REVIEW_URL; giữ nguyên review.json.
ZIP phải có đúng một bộ review.json + review.csv cạnh images/ và labels/; không dùng ZIP chỉ chứa ảnh.
'''),_cell('code','review_pack','''if MODE == 'review':
    REVIEW_PACK = WORK / 'exports' / 'car35_training_labels_to_review.zip'
    if REVIEW_PACK.exists():
        print('Gói đã có; giữ bản trước. Đổi tên output nếu cần xuất lại:', REVIEW_PACK)
    else:
        create_review_pack(DATASET_ROOT, REVIEW_PACK, per_class=REVIEW_PER_CLASS)
    print('Tải gói này, kiểm tra nhãn và đánh dấu reviewed=yes rồi chạy MODE=train:', REVIEW_PACK)
    if DOWNLOAD_RESULTS:
        from google.colab import files
        files.download(str(REVIEW_PACK))
else:
    print('Train mode: dùng REVIEW_URL hoặc LOCAL_REVIEW_ZIP đã được rà nhãn.')
'''),_cell('markdown','fine-guide','''## 2. Áp dữ liệu đã rà — giữ test riêng

Chỉ dòng reviewed=yes được áp. Ảnh cũ giữ nguyên split/group; nhãn test không được sửa.
Chỉ cần có dòng train đã reviewed=yes. Nhãn đã đúng được giữ nguyên và vẫn cho phép fine-tune tiếp.
Manifest ghi riêng số nhãn đã review, giữ nguyên, sửa đổi và ảnh bổ sung; không coi nhãn giữ nguyên là dữ liệu mới.
Ảnh mới được kiểm tra exact hash và dHash với split khác; va chạm khiến bước này dừng để rà thủ công.
dHash chỉ là heuristic, không xác nhận chuyến xe độc lập. Bộ ảnh cùng cảnh do người gán group chịu trách nhiệm.
Giữ các lớp khác và dữ liệu train cũ. Bước này tạo một bản dataset riêng, không đóng thêm ZIP dataset lớn.
'''),_cell('code','fine_prepare','''FINE_TUNE_READY = False
if MODE == 'train':
    if LOCAL_REVIEW_ZIP.strip():
        review_archive = Path(LOCAL_REVIEW_ZIP)
    else:
        assert REVIEW_URL.strip(), 'Điền REVIEW_URL bằng gói đã review; không dùng raw107 ZIP.'
        review_archive = download_drive_zip(REVIEW_URL, WORK / 'downloads' / ('review_' + drive_file_id(REVIEW_URL) + '.zip'), expected_sha256=REVIEW_SHA256)
    if REVIEW_SHA256:
        assert digest_file(review_archive) == REVIEW_SHA256.lower(), 'Review ZIP checksum khác.'
    if FINE_ROOT.exists():
        fine_manifest = json.loads((FINE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
        saved_review = fine_manifest.get('finetune_review', {})
        assert saved_review.get('base_manifest_sha256') == digest_file(DATASET_ROOT / 'manifest.json'), 'Dataset đã có thuộc baseline khác; chọn FINE_ROOT mới.'
        assert saved_review.get('review_zip_sha256') == digest_file(review_archive), 'Review ZIP đã thay đổi; chọn FINE_ROOT mới để giữ bản trước.'
        from training.data.car35_bundle import verify_car35
        fine_info = verify_car35(FINE_ROOT)
        print('Dùng lại dataset fine-tune đã kiểm tra; không sao chép lại.')
    else:
        fine_info = prepare_finetune_dataset(DATASET_ROOT, review_archive, FINE_ROOT, progress=progress)
    fine_manifest = json.loads((FINE_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    print('Review đã áp:', fine_manifest['finetune_review'])
    print('Phân bố ảnh:', fine_info['split_images'])
    print('Manifest fine-tune:', fine_info['manifest_sha256'])
    FINE_TUNE_READY = True
else:
    print('Review mode: kết thúc sau khi tải gói rà nhãn. Chưa train.')
'''),_cell('markdown','baseline-guide','''## 3. Đo baseline bằng cùng môi trường và validation

CHECKPOINT_URL là ZIP kết quả raw107; có thể tạo ZIP nhỏ chỉ chứa run/weights/best.pt để giảm tải.
Hoặc dùng LOCAL_CHECKPOINT nếu best.pt đã có trong runtime. Luôn kiểm tra SHA checkpoint đã ghim.
Đánh giá lại model gốc trên đúng validation của dataset fine-tune, cùng imgsz/batch/device/version.
Nếu sửa nhãn val, phải dùng kết quả baseline mới này để so sánh, không lấy mAP cũ làm chuẩn.
'''),_cell('code','baseline','''if FINE_TUNE_READY:
    if LOCAL_CHECKPOINT.strip():
        INITIAL_CHECKPOINT = Path(LOCAL_CHECKPOINT).resolve()
    else:
        assert CHECKPOINT_URL.strip(), 'Điền CHECKPOINT_URL bằng ZIP chứa best.pt raw107.'
        checkpoint_zip = download_drive_zip(CHECKPOINT_URL, WORK / 'downloads' / ('checkpoint_' + drive_file_id(CHECKPOINT_URL) + '.zip'))
        INITIAL_CHECKPOINT = restore_initial_checkpoint(checkpoint_zip, WORK / 'initial' / 'best.pt', expected_sha256=CHECKPOINT_SHA256, member=CHECKPOINT_MEMBER)
    assert digest_file(INITIAL_CHECKPOINT) == CHECKPOINT_SHA256.lower(), 'Initial checkpoint SHA khác.'
    baseline = evaluate_car35(INITIAL_CHECKPOINT, FINE_ROOT, BASELINE_DIR, imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE)
    print('Baseline validation:', baseline['metrics'])
'''),_cell('markdown','finetune-guide','''## 4. Fine-tune — run mới từ best.pt

Pilot mặc định 15 epoch, 640px, batch 8, AdamW lr=0.0003, patience=5, mosaic=0.1, không flip.
Optimizer và augmentation được truyền rõ vào lệnh train; không dùng optimizer=auto hay default fliplr=0.5.
Đây là cấu hình khởi đầu, không bảo đảm cải thiện. Không dùng resume cho bộ nhãn mới.
Nếu OOM, giảm batch và bắt đầu run mới. Để runtime/terminal chạy đến hết và tải kết quả về trước khi ngắt.
'''),_cell('code','finetune','''if FINE_TUNE_READY:
    BEST = finetune_car35(INITIAL_CHECKPOINT, FINE_ROOT, RUN_DIR, expected_checkpoint_sha256=CHECKPOINT_SHA256,
        epochs=EPOCHS, imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE,
        lr0=LEARNING_RATE, mosaic=MOSAIC, patience=PATIENCE)
    shutil.copytree(BASELINE_DIR, RUN_DIR / 'baseline')
    print('Fine-tuned checkpoint:', BEST)
'''),_cell('markdown','compare-guide','''## 5. So sánh trên cùng validation; test chỉ khi chốt cấu hình

Xem từng lớp, đặc biệt recall tốc độ và người đi bộ, các cặp nhầm và false positives.
mAP tổng tăng không tự chứng minh ảnh chụp thực tế được sửa. Hai ảnh cũ là regression cases, không đủ làm field test.
RUN_HELDOUT_TEST mặc định False. Chỉ bật sau khi chốt cấu hình, không dùng test để chọn hyperparameter.
Nếu ảnh đã dùng để sửa/train, không tính ảnh đó là kiểm thử độc lập. Thu thập riêng tập ảnh ô tô có nhãn.
'''),_cell('code','compare','''if FINE_TUNE_READY:
    candidate = evaluate_car35(BEST, FINE_ROOT, RUN_DIR / 'validation', imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE)
    comparison = dict(split='val', dataset_manifest_sha256=fine_info['manifest_sha256'],
        initial_checkpoint_sha256=CHECKPOINT_SHA256, candidate_checkpoint_sha256=digest_file(BEST),
        baseline=baseline['metrics'], candidate=candidate['metrics'],
        delta={k:(v-baseline['metrics'][k]) if v is not None and baseline['metrics'].get(k) is not None else None for k,v in candidate['metrics'].items()},
        baseline_per_class=baseline.get('per_class',[]), candidate_per_class=candidate.get('per_class',[]),
        test_evaluated=False, independent_field_test=False)
    if RUN_HELDOUT_TEST:
        for label, checkpoint in (('baseline',INITIAL_CHECKPOINT),('candidate',BEST)):
            evaluate_car35(checkpoint, FINE_ROOT, RUN_DIR / ('test_' + label), split='test', allow_test=True,
                imgsz=IMAGE_SIZE, batch=BATCH, device=DEVICE)
        comparison['test_evaluated'] = True
    (RUN_DIR / 'comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Baseline:', comparison['baseline'])
    print('Fine-tune:', comparison['candidate'])
    print('Delta:', comparison['delta'])
'''),_cell('markdown','regression-guide','''## 6. Thử ảnh thực tế trước khi tải kết quả

Nếu có ZIP ảnh lỗi/ảnh mới, điền REGRESSION_URL ở cấu hình. Bước này chạy cả baseline và candidate
ở confidence 0.35 và 0.05, ghi tên lớp/confidence/bbox vào photo_probe.json để thấy lỗi còn hay hết.
Không có ground truth đầy đủ thì không tính precision/recall từ vài ảnh này. Ảnh đã dùng để phát triển,
gán nhãn hoặc train chỉ là regression cases, không thuộc test độc lập.
'''),_cell('code','regression','''if FINE_TUNE_READY and REGRESSION_URL.strip():
    from training.experiments.photo_probe import probe_photos
    photo_zip = download_drive_zip(REGRESSION_URL, WORK / 'downloads' / ('photos_' + drive_file_id(REGRESSION_URL) + '.zip'))
    probe = probe_photos({'baseline': INITIAL_CHECKPOINT, 'candidate': BEST}, photo_zip,
        RUN_DIR / 'photo_probe.json', imgsz=IMAGE_SIZE, device=DEVICE)
    for label, result in probe['models'].items():
        for row in result['images']:
            print(label, row['image'], '| conf 0.35:', row['predictions']['0.35'])
else:
    print('Chưa có REGRESSION_URL; có thể bổ sung ZIP ảnh trước khi chốt model.')
'''),_cell('code','fine_export','''if FINE_TUNE_READY:
    from datetime import datetime, timezone
    target = WORK / 'exports' / (RUN_NAME + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.zip')
    RESULT_ZIP = export_car35_run(RUN_DIR, FINE_ROOT, target)
    print('Kết quả (weights + metrics + provenance, không chứa dataset ảnh):', RESULT_ZIP)
    if DOWNLOAD_RESULTS:
        from google.colab import files
        files.download(str(RESULT_ZIP))
'''),_cell('markdown','active-next','''## Vòng dữ liệu tiếp theo — active learning

Giữ ảnh chụp mới thành một pool local, chạy công cụ `training.experiments.active_learning` theo
`docs/training/car35_active_learning.md`. Công cụ ưu tiên ảnh không detect/thiếu chắc chắn và dành 25% suất
cho lấy mẫu ngẫu nhiên để không bỏ hết ảnh model tự tin nhưng sai. Đây là heuristic chọn ảnh để người rà.
Gói mới giữ các dòng đã review, thêm ảnh mới với reviewed=no và bbox AI chỉ là gợi ý.
Rà mọi biển CAR35, điền group cảnh/chuyến thật rồi mới chuyển reviewed=yes và upload ZIP qua gdown.
Hai ảnh lỗi cũ là dữ liệu phát triển/hồi quy; tập đánh giá độc lập phải dùng ảnh/cảnh khác.
''')]
    notebook['cells']=cells;notebook['metadata']['colab']['name']=TARGET.name
    return notebook


def main():
    TARGET.write_text(json.dumps(build_finetune_notebook(),ensure_ascii=False,indent=1),encoding='utf-8')
    print(TARGET)


if __name__=='__main__':main()
