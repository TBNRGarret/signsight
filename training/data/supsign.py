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
            Path(candidate.f_code.co_filename).name in ('supsign_training.py', 'supsign.py')):
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



from training.data.cache import verify_dataset, summarize_prepared_dataset, pack_dataset, restore_dataset
from training.experiments.train import train_experiment
from training.experiments.evaluate import evaluate_checkpoint
