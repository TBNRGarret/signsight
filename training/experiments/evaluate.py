"""Standalone SupSign subset preparation and YOLO11s experiments (no API changes)."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import tempfile
import zipfile

from PIL import Image
import yaml

from training.data.audit import DatasetReader, audit_dataset

from training.data.common import *
from training.data.cache import verify_dataset

def evaluate_checkpoint(checkpoint,root,output,*,split='val',allow_test=False,imgsz=640,batch=8,yolo_factory=None):
    checkpoint,root,output=Path(checkpoint),Path(root).resolve(),Path(output).resolve()
    if split not in ('val','test') or split=='test' and not allow_test:raise ValueError('Held-out test must be explicitly enabled after choosing settings')
    if output.exists():raise FileExistsError(output)
    if output.is_relative_to(root):raise ValueError('Evaluation must be outside dataset')
    dataset=verify_dataset(root)
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    detector=yolo_factory(str(checkpoint))
    names=detector.names
    names=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if detector.task!='detect' or names!=dataset['names']:raise ValueError('Checkpoint taxonomy differs from dataset')
    output.mkdir(parents=True)
    config=yaml.safe_load((root/'data.yaml').read_text());config['path']=str(root)
    runtime_data=output/'data_runtime.yaml';runtime_data.write_text(yaml.safe_dump(config),encoding='utf-8')
    result=detector.val(data=str(runtime_data),split=split,imgsz=imgsz,batch=batch,
                        project=str(output.parent),name=output.name,exist_ok=True,plots=True)
    report=dict(**dataset,split=split,checkpoint_sha256=digest_file(checkpoint),
                metrics={k:float(v) if math.isfinite(float(v)) else None for k,v in result.results_dict.items()})
    box=getattr(result,'box',None)
    if box is not None:
        report['per_class']=[dict(class_id=int(i),name=names[int(i)],precision=float(box.p[j]),
                                 recall=float(box.r[j]),map50=float(box.ap50[j]),map50_95=float(box.ap[j]))
                             for j,i in enumerate(box.ap_class_index)]
        report['classes_without_gt']=[n for i,n in enumerate(names) if i not in set(box.ap_class_index)]
    write_json(output/'evaluation_report.json',report)
    return report
