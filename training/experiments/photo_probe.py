"""Compare development photos at explicit thresholds; no accuracy claims or activation."""
import io
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from PIL import Image, ImageOps

from training.data.common import CAR35, digest_file


def probe_photos(checkpoints, archive, output, *, imgsz=640, device='0', yolo_factory=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    report=dict(usage='development_regression_only',independent_field_test=False,
                source_zip_sha256=digest_file(archive),imgsz=imgsz,models={})
    with ZipFile(archive) as source:
        entries=[m for m in source.infolist() if not m.is_dir() and PurePosixPath(m.filename).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}]
        if not entries or len(entries)>200 or sum(m.file_size for m in entries)>512*1024**2:
            raise ValueError('Photo probe ZIP needs 1..200 images, up to 512 MiB')
        if any(m.file_size>64*1024**2 or m.flag_bits&1 for m in entries):raise ValueError('Invalid photo probe member')
        for label,checkpoint in checkpoints.items():
            detector=yolo_factory(str(checkpoint));names=detector.names
            names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
            if detector.task!='detect' or names!=CAR35:raise ValueError('Photo probe checkpoint differs from CAR35')
            rows=[]
            for member in entries:
                with Image.open(io.BytesIO(source.read(member))) as image:
                    if image.width*image.height>40_000_000:raise ValueError('Photo probe image too large')
                    normalized=ImageOps.exif_transpose(image).convert('RGB')
                    row=dict(image=member.filename,predictions={})
                    for confidence in (.35,.05):
                        result=detector.predict(normalized,imgsz=imgsz,conf=confidence,device=device,verbose=False,max_det=25)[0]
                        row['predictions'][str(confidence)]=[dict(name=names[int(b.cls.item())],confidence=float(b.conf.item()),
                            bbox=list(map(float,b.xyxy[0].tolist()))) for b in result.boxes]
                    rows.append(row)
            report['models'][label]=dict(checkpoint_sha256=digest_file(checkpoint),images=rows)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        import json
        json.dump(report,stream,indent=2,allow_nan=False)
    return report
