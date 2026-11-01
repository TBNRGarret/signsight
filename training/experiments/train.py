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

def train_experiment(root,run_dir,*,epochs=80,imgsz=640,batch=8,device='0',resume=False,yolo_factory=None):
    root,run_dir=Path(root).resolve(),Path(run_dir).resolve()
    if run_dir.is_relative_to(root):raise ValueError('Training run must be outside dataset')
    if epochs<1 or imgsz<32 or batch<1:raise ValueError('Invalid training settings')
    dataset=verify_dataset(root)
    request_path=run_dir/'training_request.json'
    settings=dict(model='yolo11s.pt',epochs=epochs,imgsz=imgsz,batch=batch)
    if resume:
        if not (run_dir/'weights/last.pt').is_file() or not request_path.is_file():raise ValueError('Resume requires saved last.pt and training_request.json')
        previous=read_json(request_path)
        if previous['manifest_sha256']!=dataset['manifest_sha256']:raise ValueError('Resume dataset changed')
        if previous['settings']!=settings:raise ValueError('Resume settings changed; use the original settings or a new run')
        model=run_dir/'weights/last.pt'
    else:
        if run_dir.exists():raise FileExistsError('Run exists; set RESUME=True or choose another RUN_NAME')
        model='yolo11s.pt'
    if yolo_factory is None:
        from ultralytics import YOLO
        yolo_factory=YOLO
    detector=yolo_factory(str(model))
    if not resume:
        run_dir.mkdir(parents=True)
        write_json(request_path,dict(**dataset,settings=settings,test_evaluated=False))
    # Dataset archive remains portable; runtime absolute path lives beside the run.
    config=yaml.safe_load((root/'data.yaml').read_text(encoding='utf-8'));config['path']=str(root)
    runtime_data=run_dir/'data_runtime.yaml';runtime_data.write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    options=dict(data=str(runtime_data),epochs=epochs,imgsz=imgsz,batch=batch,device=device,
                 project=str(run_dir.parent),name=run_dir.name,exist_ok=True,workers=2,
                 seed=42,deterministic=True,cache=False,amp=True,patience=20,save=True,save_period=5,
                 fliplr=0.,flipud=0.,degrees=0.,shear=0.,perspective=0.,mixup=0.,
                 mosaic=.5,close_mosaic=min(10,epochs),plots=True)
    if resume:options['resume']=True
    detector.train(**options)
    if not (run_dir/'weights/best.pt').is_file():raise ValueError('Training did not produce best.pt')
    return run_dir/'weights/best.pt'
