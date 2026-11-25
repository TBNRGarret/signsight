"""Reviewed CAR35 additions/corrections. Never reshuffles or edits the base dataset."""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image

from training.data.car35_bundle import verify_car35
from training.data.common import CAR35, SPLITS, digest_file, read_json, write_json
from training.data.supsign import visual_hash

PRIORITY_CLASSES = ('Speed_limit_40', 'Speed_limit_50', 'Speed_limit_60',
                    'Speed_limit_70', 'Speed_limit_80', 'Pedestrian_crossing',
                    'Road_reserved_for_cars', 'No_cars_U_turn', 'No_cars_turn_right')
REVIEW_FIELDS = ('image', 'label', 'split', 'group', 'reviewed')


def _labels(content):
    """Canonical detection labels; formatting changes alone are not corrections."""
    boxes = []
    for line in content.decode('utf-8-sig').splitlines():
        if not line.strip(): continue
        fields = line.split()
        if len(fields) != 5: raise ValueError('Expected five YOLO bbox columns')
        cls = int(fields[0]); x,y,w,h = map(float, fields[1:])
        if (not 0 <= cls < 35 or not all(math.isfinite(v) for v in (x,y,w,h)) or
                min(w,h) <= 0 or min(x-w/2,y-h/2) < -1e-6 or max(x+w/2,y+h/2) > 1+1e-6):
            raise ValueError('Invalid CAR35 class or bbox')
        boxes.append((cls,x,y,w,h))
    return sorted(boxes)


def create_review_pack(base_root, target, *, per_class=15):
    """Small train-only label-editing pack, with every row initially unreviewed."""
    base_root, target = Path(base_root).resolve(), Path(target).resolve()
    if target.exists(): raise FileExistsError(target)
    if target.is_relative_to(base_root): raise ValueError('Review pack must be outside base')
    if type(per_class) is not int or not 1 <= per_class <= 100: raise ValueError('per_class must be 1..100')
    verify_car35(base_root)
    manifest = read_json(base_root/'manifest.json')
    counts = Counter(); chosen = []
    for row in sorted(manifest['images'], key=lambda r:r['sha256']):
        if row['split'] != 'train': continue
        present = {CAR35[b[0]] for b in _labels((base_root/row['label']).read_bytes())}
        wanted = present & set(PRIORITY_CLASSES)
        if any(counts[c] < per_class for c in wanted):
            chosen.append(row); counts.update(wanted)
    if not chosen: raise ValueError('No priority-class train images to review')
    metadata = dict(schema_version=1, names=CAR35,
                    base_manifest_sha256=digest_file(base_root/'manifest.json'))
    target.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(target,'x',compression=ZIP_DEFLATED) as archive:
        table = io.StringIO(newline=''); writer=csv.DictWriter(table,fieldnames=REVIEW_FIELDS);writer.writeheader()
        for row in chosen:
            image='images/'+Path(row['image']).name; label='labels/'+Path(row['label']).name
            archive.write(base_root/row['image'],image);archive.write(base_root/row['label'],label)
            writer.writerow(dict(image=image,label=label,split='train',group=row['group'],reviewed='no'))
        archive.writestr('review.csv',table.getvalue())
        archive.writestr('review.json',json.dumps(metadata,indent=2))
        archive.writestr('classes.txt','\n'.join(CAR35)+'\n')
        archive.writestr('README.txt',
            'Keep images unchanged. Correct YOLO boxes for ALL visible CAR35 signs.\n'
            'Set reviewed=yes only after checking that row. Empty labels mean verified CAR35 background.\n'
            'New images need matching labels, split=train or val, and a real capture group.\n'
            'Same physical sign/trip must stay in one split. Do not add held-out test images.\n'
            'Keep review.json, review.csv, images/ and labels/ at the ZIP root.\n')
    return target


def _review_entries(archive):
    entries = archive.infolist(); seen=set()
    if len(entries)>30000 or sum(m.file_size for m in entries)>16*1024**3:
        raise ValueError('Review ZIP exceeds limits')
    for member in entries:
        name=member.filename; path=PurePosixPath(name)
        if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or name.casefold() in seen or member.flag_bits&1
                or (member.external_attr>>16)&0o170000==0o120000):
            raise ValueError('Unsafe or duplicate review ZIP path')
        seen.add(name.casefold())
    roots = [PurePosixPath(m.filename).parent for m in entries
             if not m.is_dir() and PurePosixPath(m.filename).name == 'review.json']
    if not roots:
        raise ValueError('Missing review.json: use the edited review pack ZIP, not the dataset or an images-only ZIP')
    if len(roots) != 1:
        raise ValueError('Review ZIP contains multiple review.json files; keep exactly one review pack')
    prefix = '' if str(roots[0]) == '.' else roots[0].as_posix()+'/'
    for name in ('review.json','review.csv'):
        member = archive.NameToInfo.get(prefix+name)
        if member is None or member.is_dir():
            raise ValueError(f'Missing {prefix+name}: keep review.csv and review.json beside images/ and labels/')
        if member.file_size > 8*1024**2:
            raise ValueError(f'{prefix+name} exceeds the 8 MiB review metadata limit')
    return prefix


def _reject_cross_split_neighbours(base, rows, new_hashes, near_threshold, progress):
    """BK-tree per split: only new images are checked against other splits.

    Existing development overlap is retained, not claimed to be independent.
    This screens dHash collisions; it cannot verify real-world capture identity.
    """
    trees={s:None for s in SPLITS}; values={}
    iterator=progress(rows,desc='Screen new-image holdout overlap',unit='image') if progress else rows
    for row in iterator:
        with Image.open(base/row['image']) as image: value=visual_hash(image)
        values[row['sha256']]=value
        split=row['split']; node=trees[split]
        if node is None: trees[split]=(value,{});continue
        while True:
            distance=(value^node[0]).bit_count()
            if distance==0: break
            if distance not in node[1]: node[1][distance]=(value,{});break
            node=node[1][distance]
    for row in rows:
        if row['sha256'] not in new_hashes: continue
        value=values[row['sha256']]
        for split,tree in trees.items():
            if split==row['split'] or tree is None: continue
            pending=[tree]
            while pending:
                other,children=pending.pop();distance=(value^other).bit_count()
                if distance<=near_threshold:
                    raise ValueError('New image has a cross-split near duplicate; review holdout/capture assignment')
                pending.extend(child for edge,child in children.items()
                               if distance-near_threshold<=edge<=distance+near_threshold)


def prepare_finetune_dataset(base_root, review_zip, output, *, near_threshold=4, progress=None):
    base_root,review_zip,output=map(lambda p:Path(p).resolve(),(base_root,review_zip,output))
    if output.exists(): raise FileExistsError(output)
    if output.is_relative_to(base_root) or base_root.is_relative_to(output):
        raise ValueError('Fine-tune output must be outside base')
    if type(near_threshold) is not int or not 0<=near_threshold<=8: raise ValueError('Invalid dHash threshold')
    verify_car35(base_root)
    manifest=read_json(base_root/'manifest.json'); base_sha=digest_file(base_root/'manifest.json')
    original={r['sha256']:r for r in manifest['images']}
    with ZipFile(review_zip) as archive:
        prefix = _review_entries(archive)
        metadata=json.loads(archive.read(prefix+'review.json'))
        if metadata!=dict(schema_version=1,names=CAR35,base_manifest_sha256=base_sha):
            raise ValueError('Review taxonomy/base manifest differs; do not reuse another split patch')
        table=csv.DictReader(io.StringIO(archive.read(prefix+'review.csv').decode('utf-8-sig')))
        if table.fieldnames!=list(REVIEW_FIELDS): raise ValueError('Invalid review.csv columns')
        reviewed=list(table)
        if len(reviewed)>10000: raise ValueError('Too many review rows')
        edits={};seen_paths=set(); seen_hashes=set();new_hashes=set();groups={r['group']:r['split'] for r in original.values()}
        changed=Counter(train=0,val=0);added=Counter(train=0,val=0)
        reviewed_counts=Counter(train=0,val=0);unchanged=Counter(train=0,val=0)
        for item in reviewed:
            if item['reviewed'] not in ('yes','no'): raise ValueError('reviewed must be yes or no')
            if item['reviewed']=='no': continue
            image,label,split,group=(item[k] for k in ('image','label','split','group'))
            if (not image.startswith('images/') or not label.startswith('labels/') or
                    split not in ('train','val') or not group.strip() or group!=group.strip()):
                raise ValueError('Review requires train/val, image/label paths and capture group; test is immutable')
            if image in seen_paths or label in seen_paths: raise ValueError('Repeated review image/label')
            seen_paths.update((image,label))
            for name in (image,label):
                member = archive.NameToInfo.get(prefix+name)
                if member is None or member.is_dir():
                    raise ValueError(f'Missing review member referenced by review.csv: {prefix+name}')
            if archive.getinfo(prefix+image).file_size>64*1024**2 or archive.getinfo(prefix+label).file_size>8*1024**2:
                raise ValueError('Oversized review image/label')
            image_bytes=archive.read(prefix+image);content=archive.read(prefix+label);boxes=_labels(content)
            with Image.open(io.BytesIO(image_bytes)) as decoded:
                decoded.load(); width,height=decoded.size
            digest=hashlib.sha256(image_bytes).hexdigest()
            if digest in seen_hashes: raise ValueError('Repeated review image hash')
            seen_hashes.add(digest)
            reviewed_counts[split]+=1
            if digest in original:
                row=original[digest]
                if split!=row['split'] or group!=row['group']:
                    raise ValueError('Cannot move existing image/group across splits')
                if boxes==_labels((base_root/row['label']).read_bytes()):
                    unchanged[split]+=1
                    continue
                changed[split]+=1
            else:
                group='review:'+group
                if group in groups and groups[group]!=split: raise ValueError('Capture group crosses splits')
                suffix=PurePosixPath(image).suffix.lower()
                if suffix not in ('.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'):raise ValueError('Unsupported review image')
                row=dict(image=f'images/{split}/{digest}{suffix}',label=f'labels/{split}/{digest}.txt',
                         sha256=digest,split=split,group=group,width=width,height=height,source_path='review:'+image)
                new_hashes.add(digest);added[split]+=1
            groups[group]=split
            edits[digest]=(dict(row),image_bytes,content)
        if not reviewed_counts['train']:
            raise ValueError('No reviewed train rows: check the train images and set reviewed=yes')
        output.parent.mkdir(parents=True,exist_ok=True)
        required=sum((base_root/r['image']).stat().st_size for r in original.values())
        required+=sum(len(v[1])+len(v[2]) for v in edits.values())+64*1024**2
        if shutil.disk_usage(output.parent).free<required:raise ValueError('Not enough disk space for a separate fine-tune dataset')
        with tempfile.TemporaryDirectory(prefix='.finetune-',dir=output.parent) as temporary:
            stage=Path(temporary)/'dataset';stage.mkdir()
            rows=[];counts={s:Counter() for s in SPLITS};negatives=0
            sources=[*original.values(),*(v[0] for h,v in edits.items() if h in new_hashes)]
            iterator=progress(sources,desc='Write reviewed dataset',unit='image') if progress else sources
            for old in iterator:
                row=deepcopy(old); digest=row['sha256']
                image,label=stage/row['image'],stage/row['label']
                image.parent.mkdir(parents=True,exist_ok=True);label.parent.mkdir(parents=True,exist_ok=True)
                if digest in new_hashes: image.write_bytes(edits[digest][1])
                else: shutil.copyfile(base_root/row['image'],image)
                content=edits[digest][2] if digest in edits else (base_root/row['label']).read_bytes()
                label.write_bytes(content);row['label_sha256']=digest_file(label)
                if digest_file(image)!=digest:raise ValueError('Base/review image changed during preparation')
                boxes=_labels(content);negatives+=not boxes
                counts[row['split']].update(b[0] for b in boxes);rows.append(row)
            if new_hashes: _reject_cross_split_neighbours(stage,rows,new_hashes,near_threshold,progress)
            revised=deepcopy(manifest)
            revised.update(images=rows,negative_images=negatives,dataset_version=manifest.get('dataset_version','car35')+'_finetune_v1',
                class_counts={s:dict(counts[s]) for s in SPLITS},
                missing_classes={s:[CAR35[c] for c in range(35) if not counts[s][c]] for s in SPLITS},
                finetune_review=dict(schema_version=1,base_manifest_sha256=base_sha,
                    review_zip_sha256=digest_file(review_zip),changed_labels=dict(changed),added_images=dict(added),
                    near_threshold=near_threshold,reviewed_rows=len(seen_hashes),
                    reviewed_by_split=dict(reviewed_counts),unchanged_labels=dict(unchanged)),
                limitations=manifest.get('limitations','Development split.')+
                    ' Human-reviewed fine-tune overlay; test unchanged. Capture metadata is user supplied; dHash screening is heuristic.')
            revised.pop('raw_zip_preparation',None)
            write_json(stage/'manifest.json',revised)
            shutil.copyfile(base_root/'data.yaml',stage/'data.yaml')
            info=verify_car35(stage);write_json(stage/'dataset_report.json',info)
            stage.rename(output)
    return info
