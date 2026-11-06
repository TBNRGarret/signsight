"""Train/export a prepared CAR35 V4 dataset; never changes application serving."""
import json
import math
from pathlib import Path
import zipfile

from training.data.car35_bundle import verify_car35
from training.data.common import digest_file, read_json, write_json


def train_car35(root,run_dir,*,epochs=80,imgsz=640,batch=8,device='0',resume=False,yolo_factory=None):
    root,run_dir=Path(root).resolve(),Path(run_dir).resolve()
    if run_dir.is_relative_to(root) or root.is_relative_to(run_dir):raise ValueError('Run must be outside dataset')
    if epochs<1 or imgsz<32 or batch<1:raise ValueError('Invalid training settings')
    dataset=verify_car35(root)
    settings=dict(model='yolo11s.pt',epochs=epochs,imgsz=imgsz,batch=batch,seed=42)
    request=run_dir/'training_request.json'
    if resume:
        if not request.is_file() or not (run_dir/'weights/last.pt').is_file():
            raise ValueError('Resume requires last.pt and training_request.json in this runtime')
        previous=read_json(request)
        if previous['dataset']['manifest_sha256']!=dataset['manifest_sha256']:raise ValueError('Resume dataset changed')
        if previous['settings']!=settings:raise ValueError('Resume settings changed')
        weights=run_dir/'weights/last.pt'
    else:
        if run_dir.exists():raise FileExistsError(run_dir)
        weights='yolo11s.pt'
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    detector=yolo_factory(str(weights))
    if resume:
        names=detector.names;names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
        if detector.task!='detect' or names!=dataset['names']:raise ValueError('Resume checkpoint taxonomy differs')
    if not resume:
        run_dir.mkdir(parents=True)
        write_json(request,dict(dataset=dataset,settings=settings,test_evaluated=False))
    options=dict(data=str(root/'data.yaml'),epochs=epochs,imgsz=imgsz,batch=batch,device=device,
        project=str(run_dir.parent),name=run_dir.name,exist_ok=True,split='val',workers=2,
        seed=42,deterministic=True,cache=False,amp=True,patience=20,save=True,save_period=5,
        fliplr=0.,flipud=0.,degrees=0.,shear=0.,perspective=0.,mixup=0.,mosaic=.5,
        close_mosaic=min(10,epochs),plots=True)
    if resume:options['resume']=True
    detector.train(**options)
    best=run_dir/'weights/best.pt'
    if not best.is_file():raise ValueError('Training did not produce best.pt')
    return best


def evaluate_car35(checkpoint,root,output,*,split='val',allow_test=False,imgsz=640,batch=8,device='0',yolo_factory=None):
    if split not in ('val','test') or split=='test' and not allow_test:raise ValueError('Held-out test requires explicit opt-in')
    root,output,checkpoint=Path(root).resolve(),Path(output).resolve(),Path(checkpoint).resolve()
    if output.exists():raise FileExistsError(output)
    if output.is_relative_to(root) or root.is_relative_to(output):raise ValueError('Evaluation must be outside dataset')
    dataset=verify_car35(root)
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    detector=yolo_factory(str(checkpoint));names=detector.names
    names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if detector.task!='detect' or names!=dataset['names']:raise ValueError('Evaluation checkpoint taxonomy differs')
    output.mkdir(parents=True)
    result=detector.val(data=str(root/'data.yaml'),split=split,imgsz=imgsz,batch=batch,device=device,
                        project=str(output.parent),name=output.name,exist_ok=True,plots=True)
    report=dict(dataset=dataset,split=split,split_images=dataset['split_images'][split],
                checkpoint_sha256=digest_file(checkpoint),independent_field_test=False,
                metrics={k:float(v) if math.isfinite(float(v)) else None for k,v in result.results_dict.items()})
    box=getattr(result,'box',None)
    if box is not None:
        report['per_class']=[dict(class_id=int(c),name=names[int(c)],precision=float(box.p[j]),
            recall=float(box.r[j]),map50=float(box.ap50[j]),map50_95=float(box.ap[j])) for j,c in enumerate(box.ap_class_index)]
    write_json(output/'evaluation_report.json',report)
    return report


def export_car35_run(run_dir,root,target):
    run_dir,root,target=Path(run_dir).resolve(),Path(root).resolve(),Path(target).resolve()
    if target.exists():raise FileExistsError(target)
    if target.is_relative_to(run_dir) or target.is_relative_to(root):raise ValueError('Export must be outside run/dataset')
    if not any((run_dir/'weights'/n).is_file() for n in ('best.pt','last.pt')):raise ValueError('No checkpoint to export yet')
    dataset=verify_car35(root)
    request=read_json(run_dir/'training_request.json')
    if request['dataset']['manifest_sha256']!=dataset['manifest_sha256']:raise ValueError('Export dataset changed')
    handoff=dict(schema_version=1,dataset=dataset,settings=request['settings'],independent_field_test=False,
        checkpoints={n:digest_file(run_dir/'weights'/n) for n in ('best.pt','last.pt') if (run_dir/'weights'/n).is_file()},
        limitations='Development CAR35 V4; scene overlap and rare holdout classes remain. Review before activation.')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        for path in sorted(run_dir.rglob('*')):
            if path.is_file() and not path.is_symlink():archive.write(path,'run/'+path.relative_to(run_dir).as_posix())
        for name in ('manifest.json','data.yaml','dataset_report.json','class_counts.csv','README.md'):
            if (root/name).is_file():archive.write(root/name,'dataset/'+name)
        archive.writestr('handoff.json',json.dumps(handoff,ensure_ascii=False,indent=2))
    return target
