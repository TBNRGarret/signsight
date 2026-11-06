"""Restore and verify a prepared CAR35 V4 ZIP without source data or re-splitting."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

import yaml
from training.data.common import CAR35, SPLITS, digest_file


def verify_car35(root, *, expected_manifest_sha256='', workers=8):
    root=Path(root).resolve();manifest_file=root/'manifest.json'
    if expected_manifest_sha256 and digest_file(manifest_file)!=expected_manifest_sha256:
        raise ValueError('CAR35 manifest SHA-256 mismatch')
    manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('kind')!='car35_folder_development_v4' or manifest.get('names')!=CAR35:
        raise ValueError('Expected prepared CAR35 V4 taxonomy, not raw SupSign or a V3 cache')
    config=yaml.safe_load((root/'data.yaml').read_text(encoding='utf-8'))
    if config!=dict(train='images/train',val='images/val',test='images/test',names=CAR35):
        raise ValueError('Unsafe or changed CAR35 data.yaml')
    if manifest.get('independent_field_test') is not False:
        raise ValueError('This development bundle is not an independent field test')
    if type(workers) is not int or not 1<=workers<=32:raise ValueError('Invalid worker count')
    images,labels,hashes,groups=set(),set(),set(),{}
    counts={s:Counter() for s in SPLITS};sizes=Counter()
    def check(row):
        split=row['split'];image,label=(root/row[k] for k in ('image','label'));sha=row['sha256']
        if (split not in SPLITS or not re.fullmatch('[0-9a-f]{64}',sha)
            or image.parent!=root/'images'/split or image.stem!=sha
            or image.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
            or label!=root/'labels'/split/(sha+'.txt')
            or not image.resolve().is_relative_to(root) or not label.resolve().is_relative_to(root)):
            raise ValueError('Unsafe manifest image/label path')
        content=label.read_bytes()
        if digest_file(image)!=sha or hashlib.sha256(content).hexdigest()!=row['label_sha256']:
            raise ValueError('CAR35 image/label hash changed')
        current=Counter()
        for line in content.decode('utf-8').splitlines():
            if not line.strip():continue
            fields=line.split()
            if len(fields)!=5:raise ValueError('Invalid detection label')
            c=int(fields[0]);x,y,w,h=map(float,fields[1:])
            if (not 0<=c<35 or not all(math.isfinite(v) for v in (x,y,w,h)) or min(w,h)<=0
                or min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6):
                raise ValueError('Invalid CAR35 class/bbox')
            current[c]+=1
        return row,image,label,current
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row,image,label,current in pool.map(check,manifest['images']):
            if row['sha256'] in hashes or (row['group'] in groups and groups[row['group']]!=row['split']):
                raise ValueError('Duplicate hash or cross-split CAR35 group')
            images.add(image);labels.add(label);hashes.add(row['sha256']);groups[row['group']]=row['split']
            sizes[row['split']]+=1;counts[row['split']].update(current)
    actual_labels=set((root/'labels').rglob('*.*'))
    allowed_caches={root/'labels'/(s+suffix) for s in SPLITS for suffix in ('.cache','.cache.npy')}
    for cache in actual_labels & allowed_caches:
        if cache.is_symlink() or not cache.is_file() or not cache.resolve().is_relative_to(root):
            raise ValueError('Unsafe YOLO label cache path')
    if images!=set((root/'images').rglob('*.*')) or labels!=actual_labels-allowed_caches:
        raise ValueError('CAR35 image/label inventory changed')
    if set(sizes)!=set(SPLITS):raise ValueError('Empty CAR35 split')
    for split in SPLITS:
        recorded={int(k):v for k,v in manifest['class_counts'][split].items() if v}
        if recorded!=dict(counts[split]):raise ValueError('CAR35 class counts changed')
    if any(not counts['train'][c] for c in range(35)):raise ValueError('Missing CAR35 train class')
    return dict(images=len(images),boxes=sum(sum(c.values()) for c in counts.values()),names=list(CAR35),
                split_images=dict(sizes),split_groups=dict(Counter(groups.values())),
                class_counts={s:dict(counts[s]) for s in SPLITS},groups=len(groups),
                manifest_sha256=digest_file(manifest_file),independent_field_test=False,
                limitations=manifest.get('limitations','Development split; scene overlap may remain.'))


def restore_car35_bundle(archive,output,*,expected_sha256,expected_manifest_sha256=''):
    archive,output=Path(archive).resolve(),Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    if not re.fullmatch('[0-9a-fA-F]{64}',expected_sha256 or ''):
        raise ValueError('CAR35 archive SHA-256 is required')
    if digest_file(archive)!=expected_sha256.lower():raise ValueError('CAR35 ZIP checksum mismatch')
    with zipfile.ZipFile(archive) as source:
        entries=source.infolist();seen=set()
        for member in entries:
            name=member.filename;path=PurePosixPath(name)
            if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or name.casefold() in seen or (member.external_attr>>16)&0o170000==0o120000
                or member.flag_bits&1):raise ValueError('Unsafe or duplicate CAR35 ZIP member')
            seen.add(name.casefold())
        if not {'data.yaml','manifest.json'}<=seen:raise ValueError('ZIP is not a flat prepared CAR35 bundle')
        required=sum(m.file_size for m in entries)+1024**3
        output.parent.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(output.parent).free<required:raise ValueError('Not enough disk space to restore CAR35')
        with tempfile.TemporaryDirectory(prefix='.car35-restore-',dir=output.parent) as temporary:
            stage=Path(temporary)/'dataset';stage.mkdir()
            for member in entries:
                if member.is_dir():continue
                target=stage/member.filename;target.parent.mkdir(parents=True,exist_ok=True)
                with source.open(member) as stream,target.open('wb') as dest:shutil.copyfileobj(stream,dest)
            info=verify_car35(stage,expected_manifest_sha256=expected_manifest_sha256)
            stage.rename(output)
    return info
