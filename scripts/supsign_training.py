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

from scripts.dataset_eda import DatasetReader, audit_dataset

CAR35 = [
    'Speed_limit_40', 'Speed_limit_50', 'Speed_limit_60', 'Speed_limit_70', 'Speed_limit_80',
    'No_entry', 'No_cars', 'No_cars_turn_left', 'No_cars_turn_right',
    'No_turn_left', 'No_turn_right', 'No_U_turn', 'No_cars_U_turn',
    'No_straight_ahead', 'No_turn_left_and_U_turn', 'No_turn_left_and_right',
    'No_parking', 'No_stopping_and_parking', 'No_parking_odd_days', 'No_parking_even_days',
    'Go_straight', 'Keep_right', 'Roundabout', 'One_way_road', 'Road_reserved_for_cars',
    'Pedestrian_crossing', 'Children_crossing', 'Road_works', 'Slow_down',
    'Dangerous_curve_left', 'Dangerous_curve_right',
    'No_overtaking', 'End_no_overtaking', 'Give_way', 'End_all_prohibitions',
]
SPLITS = ('train', 'val', 'test')
VERSION = 1


def digest_file(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
        return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def recipe(classes=CAR35, seed=42, block_size=100, near_threshold=4, groups=None):
    # Implementation hash invalidates caches when embedded preparation code changes.
    group_digest = hashlib.sha256(json.dumps(groups, sort_keys=True).encode()).hexdigest()
    return dict(version=VERSION, classes=list(classes), seed=seed, block_size=block_size,
                near_threshold=near_threshold, groups_sha256=group_digest,
                implementation_sha256=digest_file(__file__),
                reader_sha256=digest_file(Path(__file__).with_name('dataset_eda.py')))


def visual_hash(image):
    grey = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(grey.tobytes()); result = 0
    for y in range(8):
        for x in range(8): result = (result << 1) | (pixels[y*9+x] > pixels[y*9+x+1])
    return result


def cluster_records(rows, *, groups=None, block_size=100, near_threshold=4, progress=None):
    """Union supplied captures, filename blocks and dHash neighbours transitively.

    Filename blocks / visual hashes are only development heuristics, never proof of
    independent trips or physical signs. Explicit groups replace filename blocks.
    """
    if block_size < 1 or (near_threshold is not None and not 0 <= near_threshold <= 8):
        raise ValueError('Invalid grouping settings')
    parent = list(range(len(rows)))
    def find(i):
        while i != parent[i]: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parent[max(a,b)] = min(a,b)
    seen = {}
    tree = None
    grouping = progress(rows, desc='Group related images', unit='image') if progress else rows
    for index, row in enumerate(grouping):
        for alias in row['aliases']:
            relative = alias.split('!/', 1)[-1]
            if groups is not None:
                group = groups.get(relative, groups.get(alias))
                if not isinstance(group, str) or not group.strip():
                    raise ValueError(f'Missing capture group: {relative}')
                key = ('capture', group.strip())
            else:
                match = re.fullmatch(r'(.*?)([0-9]+)', PurePosixPath(relative).stem)
                key = ('filename', match[1], int(match[2]) // block_size) if match else ('image', row['sha256'])
            if key in seen: union(index, seen[key])
            else: seen[key] = index
        if near_threshold is None: continue
        value = row['visual_hash']
        if tree is None: tree = (value, index, {}); continue
        # BK tree lookup: no O(n^2) all-pairs hash matrix.
        pending = [tree]
        while pending:
            other, representative, children = pending.pop()
            distance = (value ^ other).bit_count()
            if distance <= near_threshold: union(index, representative)
            pending.extend(child for edge, child in children.items()
                           if distance-near_threshold <= edge <= distance+near_threshold)
        node = tree
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0: break
            if distance not in node[2]: node[2][distance] = (value, index, {}); break
            node = node[2][distance]
    return [f'g{find(i):06d}' for i in range(len(rows))]


def choose_splits(rows, names, seed):
    grouped = defaultdict(list)
    for row in rows: grouped[row['group']].append(row)
    if len(grouped) < 3: raise ValueError('Need at least 3 independent candidate groups; provide capture groups')
    keys = sorted(grouped)
    group_counts = {key: Counter(int(line.split()[0]) for row in values for line in row['lines'])
                    for key, values in grouped.items()}
    total = sum(group_counts.values(), Counter())
    absent = [names[i] for i in range(len(names)) if not total[i]]
    if absent: raise ValueError('No usable training annotations for classes: '+str(absent))
    support = {i: {key for key in keys if group_counts[key][i]} for i in range(len(names))}
    forced_train = {next(iter(groups)) for groups in support.values() if len(groups) == 1}
    eligible = [key for key in keys if key not in forced_train]
    # Removing two holdout groups loses coverage only for a class supported by
    # exactly those two groups. This finds a feasible seed pair without splitting
    # a group or depending on forty random attempts to rescue a rare class.
    incompatible = {frozenset(groups) for groups in support.values() if len(groups) == 2}
    ratios = {'train': .7, 'val': .15, 'test': .15}
    def balance(sizes):
        return sum(abs(sizes[s]/len(rows)-ratios[s]) for s in SPLITS)
    best = None
    for trial in range(40):
        rng = random.Random(seed+trial)
        candidates = eligible.copy(); rng.shuffle(candidates)
        pair = next(((a,b) for i,a in enumerate(candidates) for b in candidates[i+1:]
                     if frozenset((a,b)) not in incompatible), None)
        if pair is None:
            raise ValueError('Cannot preserve train class coverage with non-empty val/test groups; '
                             'provide more independent capture groups, or explicitly revise the taxonomy')
        assignments = dict.fromkeys(keys, 'train')
        sizes = Counter(train=len(rows))
        counts = {'train': total.copy(), 'val': Counter(), 'test': Counter()}
        for key, split in zip(pair, ('val','test')):
            assignments[key] = split
            sizes['train'] -= len(grouped[key]); sizes[split] += len(grouped[key])
            counts['train'].subtract(group_counts[key]); counts[split].update(group_counts[key])
        order = keys.copy(); rng.shuffle(order)
        order.sort(key=lambda k: -len(grouped[k]))
        missing_count = sum(not counts[s][i] for s in ('val','test') for i in range(len(names)))
        score = missing_count*1e6 + balance(sizes)
        for key in order:
            gc = group_counts[key]
            if assignments[key] != 'train' or any(counts['train'][c] <= n for c,n in gc.items()):
                continue
            choices = []
            for split in ('val','test'):
                proposed = sizes.copy()
                proposed['train'] -= len(grouped[key]); proposed[split] += len(grouped[key])
                remaining = missing_count-sum(not counts[split][c] for c in gc)
                choices.append((remaining*1e6+balance(proposed), split, remaining, proposed))
            cost, split, remaining, proposed = min(choices, key=lambda v: v[0])
            if cost < score:
                assignments[key] = split; sizes = proposed; missing_count = remaining; score = cost
                counts['train'].subtract(gc); counts[split].update(gc)
        missing = {s: [i for i in range(len(names)) if not counts[s][i]] for s in SPLITS}
        if best is None or score < best[0]: best = score, assignments, counts, missing
    _, assignments, counts, missing = best
    if missing['train']: raise ValueError('Missing train classes after grouping: '+str([names[i] for i in missing['train']]))
    for row in rows: row['split'] = assignments[row['group']]
    return counts, {s: [names[i] for i in missing[s]] for s in SPLITS}


def prepare_supsign(source, output, *, classes=CAR35, groups=None, seed=42,
                    block_size=100, near_threshold=4, progress=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or not zipfile.is_zipfile(source): raise ValueError('SOURCE_ZIP must be an existing YOLO ZIP')
    if output.exists(): raise FileExistsError(output)
    if not classes or len(set(classes)) != len(classes): raise ValueError('Choose unique target classes')
    settings = recipe(classes, seed, block_size, near_threshold, groups)
    excluded, rows, by_hash = [], [], defaultdict(list)
    with DatasetReader(source) as reader:
        if reader.warnings: raise ValueError('Source archive warnings: '+str(reader.warnings[:3]))
        report = audit_dataset(reader, 'supsign', hash_limit=None, verify_decode=True,
                               annotation_format='yolo', progress=progress)
        source_names = {name for catalog in report['summary']['class_maps'] for name in catalog['names'].values()}
        missing = set(classes)-source_names
        if missing: raise ValueError('Missing source classes: '+str(sorted(missing)))
        boxes = defaultdict(list)
        for box in report['boxes']: boxes[box['path']].append(box)
        for image in report['images']:
            status = image['annotation_status']
            if status not in ('annotated','empty_annotation'):
                excluded.append(dict(source_path=image['path'],reason=status));continue
            if any(not b['class_mapped'] for b in boxes[image['path']]):
                raise ValueError('Unmapped source class metadata')
            by_hash[image['sha256']].append(image)
        duplicates_removed = 0
        candidates = sorted(by_hash.items())
        if progress: candidates = progress(candidates, desc='Deduplicate / visual hashes', unit='image')
        for digest, copies in candidates:
            # Compare ALL source labels, not just selected classes. Disagreement is quarantined.
            signatures = {tuple(sorted((b['class_name'], *(round(b[k],8) for k in
                          ['x_norm','y_norm','width_norm','height_norm'])) for b in boxes[v['path']])) for v in copies}
            if len(signatures) != 1:
                excluded.extend(dict(source_path=v['path'],reason='conflicting_duplicate_labels') for v in copies);continue
            representative = min(copies,key=lambda v:v['path']); lines = []
            for b in boxes[representative['path']]:
                if b['class_name'] not in classes:continue
                x,y = b['x_norm']+b['width_norm']/2,b['y_norm']+b['height_norm']/2
                lines.append(f"{classes.index(b['class_name'])} {x:.10f} {y:.10f} {b['width_norm']:.10f} {b['height_norm']:.10f}")
            with reader.open(representative['path']) as stream, Image.open(stream) as image:
                value = visual_hash(image) if near_threshold is not None else 0
            rows.append(dict(source_path=representative['path'],aliases=sorted(v['path'] for v in copies),
                             sha256=digest,lines=lines,visual_hash=value))
            duplicates_removed += len(copies)-1
        if not rows: raise ValueError('No usable images remain')
        for row, group in zip(rows,cluster_records(rows,groups=groups,block_size=block_size,
                                                 near_threshold=near_threshold,progress=progress)):
            row['group'] = group
        report['_split_provenance'] = 'provided_capture_groups' if groups is not None else 'development_heuristic'
        return finish_supsign_preparation(source, output, rows=rows, report=report,
            excluded=excluded, duplicates_removed=duplicates_removed, settings=settings, progress=progress)


def finish_supsign_preparation(source, output, *, rows, report, excluded,
                               duplicates_removed, settings, progress=None):
    """Finish an audited/grouped snapshot; verify copied image hashes before publishing."""
    from copy import deepcopy
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists(): raise FileExistsError(output)
    rows = deepcopy(rows)  # Keep failed-frame state available if finalization needs retry.
    classes, seed = settings['classes'], settings['seed']
    counts, missing = choose_splits(rows,classes,seed)
    with DatasetReader(source) as reader:
        if reader.warnings: raise ValueError('Source archive warnings: '+str(reader.warnings[:3]))
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.supsign-',dir=output.parent) as temporary:
            stage = Path(temporary)/'dataset';stage.mkdir()
            writing = progress(rows, desc='Write prepared images', unit='image') if progress else rows
            for row in writing:
                suffix = PurePosixPath(row['source_path']).suffix.lower()
                row['image'] = f"images/{row['split']}/{row['sha256']}{suffix}"
                row['label'] = f"labels/{row['split']}/{row['sha256']}.txt"
                image, label = stage/row['image'], stage/row['label']
                image.parent.mkdir(parents=True,exist_ok=True);label.parent.mkdir(parents=True,exist_ok=True)
                with reader.open(row['source_path']) as stream, image.open('wb') as target:shutil.copyfileobj(stream,target)
                if digest_file(image) != row['sha256']:raise ValueError('Source image changed during preparation')
                label.write_text('\n'.join(row.pop('lines'))+'\n',encoding='utf-8')
                row['label_sha256'] = digest_file(label);row.pop('visual_hash')
            manifest = dict(kind='supsign_car35_experiment',recipe=settings,names=list(classes),
                source_zip_sha256=digest_file(source),source_summary=report['summary'],
                images=rows,excluded=excluded,issues=report['issues'],duplicates_removed=duplicates_removed,
                class_counts={s:dict(counts[s]) for s in SPLITS},missing_classes=missing,
                split_provenance=report.get('_split_provenance', 'development_heuristic'),
                independent_field_test=False,
                limitations='Exact-byte duplicates removed; dHash and filename blocks are heuristics. '
                            'An independent car/windshield field test is still required. '
                            'Source-negative/other-class images are negatives only for the selected taxonomy.')
            write_json(stage/'manifest.json',manifest)
            config=dict(path='.',train='images/train',val='images/val',test='images/test',names=list(classes))
            (stage/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
            stage.rename(output)
    return manifest


def recover_failed_preparation(traceback, *, progress=None):
    """Resume the split failure in the current Python session, without re-auditing.

    The traceback must retain prepare_supsign's fully audited and grouped rows.
    Never accepts an arbitrary saved file as proof that the source was audited.
    """
    frame = None
    while traceback is not None:
        candidate = traceback.tb_frame
        if (candidate.f_code.co_name == 'prepare_supsign' and
            Path(candidate.f_code.co_filename).name == 'supsign_training.py'):
            state = candidate.f_locals
            if (state.get('rows') and all('group' in row and 'lines' in row for row in state['rows'])
                and all(key in state for key in ('source','output','report','excluded','duplicates_removed'))):
                frame = dict(state)
        traceback = traceback.tb_next
    if frame is None:
        raise ValueError('No completed preparation snapshot in traceback; keep the original failed runtime '
                         'or rerun preparation with the updated notebook')
    def inventory(reader):
        return {name: (member.CRC, member.file_size) for name, (_, member, _) in reader.entries.items()
                if member is not None}
    original = frame.get('reader')
    if original is None: raise ValueError('Missing source inventory in preparation traceback')
    with DatasetReader(frame['source']) as current:
        if inventory(original) != inventory(current):
            raise ValueError('Source ZIP changed since the failed preparation; rerun the audit')
    report = dict(frame['report'])
    report['_split_provenance'] = 'provided_capture_groups' if frame.get('groups') is not None else 'development_heuristic'
    settings = recipe(frame['classes'], frame['seed'], frame['block_size'],
                      frame['near_threshold'], frame.get('groups'))
    return finish_supsign_preparation(frame['source'], frame['output'], rows=frame['rows'],
        report=report, excluded=frame['excluded'], duplicates_removed=frame['duplicates_removed'],
        settings=settings, progress=progress)


def verify_dataset(root):
    root = Path(root).resolve();manifest = read_json(root/'manifest.json')
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
        if expected_recipe is not None and manifest['recipe']!=expected_recipe:raise ValueError('Cache recipe changed; choose a new cache version')
        verify_dataset(stage);stage.rename(output)
    return manifest


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
