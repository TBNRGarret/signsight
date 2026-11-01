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
from training.compatibility import require_compatible_recipe, dataset_content_fingerprint

def verify_dataset(root):
    root = Path(root).resolve();manifest = read_json(root/'manifest.json')
    require_compatible_recipe(manifest['recipe'])
    config = yaml.safe_load((root/'data.yaml').read_text(encoding='utf-8'))
    if config != dict(path='.',train='images/train',val='images/val',test='images/test',names=manifest['names']):
        raise ValueError('Dataset YAML changed')
    hashes,groups,expected,labels = set(),{},set(),set()
    for row in manifest['images']:
        image,label = root/row['image'],root/row['label'];split=row['split']
        if split not in SPLITS or image.parent != root/'images'/split or label != root/'labels'/split/(image.stem+'.txt'):
            raise ValueError('Unsafe or misplaced manifest path')
        if row['sha256'] in hashes or (row['group'] in groups and groups[row['group']]!=split):
            raise ValueError('Duplicate image or cross-split capture group')
        if digest_file(image)!=row['sha256'] or digest_file(label)!=row['label_sha256']:raise ValueError('Dataset image/label changed')
        hashes.add(row['sha256']);groups[row['group']]=split;expected.add(image);labels.add(label)
    if expected!=set((root/'images').rglob('*.*')) or labels!=set((root/'labels').rglob('*.txt')):
        raise ValueError('Dataset inventory changed')
    if {r['split'] for r in manifest['images']}!=set(SPLITS):raise ValueError('Empty dataset split')
    return dict(images=len(expected),names=manifest['names'],manifest_sha256=digest_file(root/'manifest.json'),
                dataset_content_sha256=dataset_content_fingerprint(manifest),
                independent_field_test=manifest['independent_field_test'],split_provenance=manifest['split_provenance'])


def summarize_prepared_dataset(root, *, imgsz=640):
    """EDA of the exact prepared training set, without changing images/labels/splits."""
    root = Path(root).resolve()
    if type(imgsz) is not int or imgsz < 32:
        raise ValueError('Invalid EDA input image size')
    manifest = read_json(root / 'manifest.json')
    names = manifest['names']
    images, boxes = [], []
    counts = {split: Counter() for split in SPLITS}
    negatives = 0
    for row in manifest['images']:
        # Preparation/cache verification already checked hashes and decoded images.
        with Image.open(root / row['image']) as image:
            width, height = image.size
        entries = [line.split() for line in (root / row['label']).read_text().splitlines() if line.strip()]
        if not entries:
            negatives += 1
        images.append(dict(image=row['image'], split=row['split'], group=row['group'],
                           width=width, height=height, boxes=len(entries)))
        for entry in entries:
            cls = int(entry[0]); _, _, w, h = map(float, entry[1:])
            counts[row['split']][cls] += 1
            scale = imgsz / max(width, height)
            boxes.append(dict(image=row['image'], split=row['split'], class_id=cls, name=names[cls],
                              width_px=w*width, height_px=h*height, area_fraction=w*h,
                              aspect_ratio=w*width/(h*height),
                              short_side_at_input=min(w*width,h*height)*scale))
    catalogue = [dict(class_id=i, name=name, **{s: counts[s][i] for s in SPLITS})
                 for i, name in enumerate(names)]
    exclusions = Counter(row['reason'] for row in manifest['excluded'])
    summary = dict(images=len(images), boxes=len(boxes), negative_images=negatives,
                   groups=len({r['group'] for r in images}), input_size=imgsz,
                   boxes_under_16px=sum(b['short_side_at_input'] < 16 for b in boxes),
                   duplicates_removed=manifest['duplicates_removed'], excluded_images=len(manifest['excluded']),
                   exclusion_reasons=dict(exclusions), missing_classes=manifest['missing_classes'],
                   split_provenance=manifest['split_provenance'], independent_field_test=False,
                   source_summary=manifest['source_summary'], limitations=manifest['limitations'])
    return dict(summary=summary, class_counts=catalogue, images=images, boxes=boxes)


def pack_dataset(root,target):
    root,target=Path(root).resolve(),Path(target).resolve()
    if target.is_relative_to(root):raise ValueError('Dataset cache must be outside the dataset')
    if target.exists() or target.with_suffix(target.suffix+'.sha256').exists():raise FileExistsError(target)
    verify_dataset(root);target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix(target.suffix+'.part')
    if temporary.exists():raise FileExistsError(temporary)
    try:
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(root.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(root).as_posix())
        temporary.rename(target)
        target.with_suffix(target.suffix+'.sha256').write_text(digest_file(target),encoding='utf-8')
    finally:
        if temporary.exists():temporary.unlink()
    return target


def restore_dataset(source,output,*,expected_recipe=None):
    source,output=Path(source),Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    if digest_file(source)!=source.with_suffix(source.suffix+'.sha256').read_text().strip():
        raise ValueError('Dataset cache checksum mismatch')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as archive, tempfile.TemporaryDirectory(prefix='.restore-',dir=output.parent) as temporary:
        stage=Path(temporary)/'dataset';stage.mkdir();seen=set()
        for member in archive.infolist():
            relative=PurePosixPath(member.filename)
            if (relative.is_absolute() or '..' in relative.parts or '\\' in member.filename
                    or ':' in member.filename or member.filename in seen
                    or (member.external_attr>>16)&0o170000==0o120000):raise ValueError('Unsafe cache ZIP path')
            seen.add(member.filename)
            if member.is_dir():continue
            path=stage/relative;path.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(member) as stream,path.open('wb') as target:shutil.copyfileobj(stream,target)
        manifest=read_json(stage/'manifest.json')
        require_compatible_recipe(manifest['recipe'], expected_recipe)
        verify_dataset(stage);stage.rename(output)
    return manifest
