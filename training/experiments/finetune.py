"""Start a new CAR35 fine-tune run from a verified local checkpoint."""
from pathlib import Path
import math
import re
import tempfile
from zipfile import ZipFile

from training.data.car35_bundle import verify_car35
from training.data.common import CAR35, digest_file, read_json, write_json


def restore_initial_checkpoint(archive, target, *, expected_sha256, member='run/weights/best.pt'):
    """Read exactly the requested member; never extracts unrelated archive paths."""
    target=Path(target).resolve()
    if not re.fullmatch('[a-fA-F0-9]{64}',expected_sha256 or ''):raise ValueError('Pin initial checkpoint SHA-256')
    if target.exists():
        if digest_file(target)!=expected_sha256.lower():raise ValueError('Existing initial checkpoint differs')
        return target
    target.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(archive) as source, tempfile.TemporaryDirectory(prefix='.initial-',dir=target.parent) as tmp:
        entries=[m for m in source.infolist() if m.filename==member]
        if len(entries)!=1 or entries[0].flag_bits&1 or entries[0].file_size>256*1024**2:
            raise ValueError('Missing/duplicate/oversized initial checkpoint member')
        staged=Path(tmp)/'best.pt'
        with source.open(entries[0]) as src,staged.open('wb') as dst:
            import shutil
            shutil.copyfileobj(src,dst)
        if digest_file(staged)!=expected_sha256.lower():raise ValueError('Initial checkpoint SHA-256 mismatch')
        if target.exists():raise FileExistsError(target)
        staged.rename(target)
    return target


def finetune_car35(checkpoint, root, run_dir, *, expected_checkpoint_sha256,
                   epochs=15, imgsz=640, batch=8, device='0', lr0=.0003,
                   mosaic=.1, patience=5, yolo_factory=None):
    checkpoint,root,run_dir=map(lambda p:Path(p).resolve(),(checkpoint,root,run_dir))
    if (not re.fullmatch('[a-fA-F0-9]{64}',expected_checkpoint_sha256 or '') or
            not checkpoint.is_file() or digest_file(checkpoint)!=expected_checkpoint_sha256.lower()):
        raise ValueError('Initial checkpoint SHA-256 mismatch or checkpoint missing')
    if run_dir.exists():raise FileExistsError(run_dir)
    if run_dir.is_relative_to(root) or root.is_relative_to(run_dir):raise ValueError('Run must be outside dataset')
    if any(type(v) is not int or v<minimum for v,minimum in ((epochs,1),(imgsz,32),(batch,1))):
        raise ValueError('Invalid fine-tune settings')
    if (not math.isfinite(lr0) or not 0 < lr0 <= .001 or not math.isfinite(mosaic) or
            not 0 <= mosaic <= .2 or type(patience) is not int or patience < 1):
        raise ValueError('Pilot requires lr0 in (0,.001], mosaic in [0,.2] and positive patience')
    dataset=verify_car35(root);review=read_json(root/'manifest.json').get('finetune_review',{})
    if not (review.get('reviewed_rows',0) or review.get('changed_labels',{}).get('train',0)
            or review.get('added_images',{}).get('train',0)):
        raise ValueError('Fine-tune requires reviewed data; unchanged correct labels are accepted')
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    detector=yolo_factory(str(checkpoint));names=detector.names
    names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if detector.task!='detect' or names!=CAR35:raise ValueError('Initial checkpoint taxonomy differs from CAR35')
    options=dict(data=str(root/'data.yaml'),epochs=epochs,imgsz=imgsz,batch=batch,device=device,
        project=str(run_dir.parent),name=run_dir.name,exist_ok=True,split='val',workers=2,
        optimizer='AdamW',lr0=lr0,lrf=.1,cos_lr=True,warmup_epochs=2.,warmup_bias_lr=0.,
        patience=patience,freeze=0,resume=False,seed=42,deterministic=True,cache=False,amp=True,
        fliplr=0.,flipud=0.,degrees=0.,shear=0.,perspective=0.,mixup=0.,mosaic=mosaic,
        close_mosaic=min(5,epochs),save=True,save_period=5,plots=True)
    run_dir.mkdir(parents=True)
    write_json(run_dir/'training_request.json',dict(dataset=dataset,test_evaluated=False,
        settings=dict(model='yolo11s_car35_finetune',initial_checkpoint_sha256=digest_file(checkpoint),
                      epochs=epochs,imgsz=imgsz,batch=batch,optimizer='AdamW',lr0=lr0,seed=42,
                      mosaic=mosaic,patience=patience,fliplr=0.,flipud=0.),
        train_options=options,review=review))
    detector.train(**options)
    best=run_dir/'weights/best.pt'
    if not best.is_file():raise ValueError('Fine-tune did not produce best.pt')
    return best
