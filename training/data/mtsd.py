"""Annotation-only MTSD reconnaissance; no images downloaded or labels approved."""
from collections import Counter
import json
from pathlib import PurePosixPath
import re
from zipfile import ZipFile


def inspect_mtsd(source):
    """Read the provider's annotation ZIP before acquiring large image archives.

    Only exact g1 maximum-speed labels are proposed, never approved mappings.
    Other variants/units and annotations on the same image require visual review.
    Train membership must come from the supplied official split lists.
    """
    labels, image_counts, candidates = Counter(), Counter(), []
    explicit_partial = 0
    schema = None
    annotation_count = 0
    with ZipFile(source) as archive:
        files = [m for m in archive.infolist() if not m.is_dir()]
        names = [m.filename for m in files]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate ZIP members')
        splits = {}
        for split in ('train', 'val', 'test'):
            matches = [m for m in files if PurePosixPath(m.filename).name == split + '.txt']
            if len(matches) > 1:
                raise ValueError('Ambiguous split list: ' + split + '.txt')
            if not matches:
                if split == 'train':
                    raise ValueError('Missing official train.txt in annotation ZIP; supply the provider annotation/splits bundle')
                splits[split] = set()
                continue
            if matches[0].file_size > 8 * 1024**2:
                raise ValueError('Oversized split list')
            ids = archive.read(matches[0]).decode('utf-8-sig').splitlines()
            splits[split] = {PurePosixPath(key.strip()).stem for key in ids if key.strip()}
        if any(splits[a] & splits[b] for a, b in (('train', 'val'), ('train', 'test'), ('val', 'test'))):
            raise ValueError('Official split lists overlap')
        seen_ids = set()
        for member in sorted(files, key=lambda m: m.filename):
            if PurePosixPath(member.filename).suffix.lower() != '.json':
                continue
            if member.file_size > 16 * 1024**2:
                raise ValueError('Oversized annotation: ' + member.filename)
            content = json.loads(archive.read(member))
            if not isinstance(content, dict) or 'objects' not in content:
                continue  # E.g. provider class/config metadata.
            objects = content['objects']
            if not isinstance(objects, list) or any(not isinstance(o, dict) or not isinstance(o.get('label'), str) for o in objects):
                raise ValueError('Unexpected MTSD objects schema: ' + member.filename)
            key = PurePosixPath(member.filename).stem
            if key in seen_ids:
                raise ValueError('Duplicate annotation image key: ' + key)
            seen_ids.add(key)
            annotation_count += 1
            if schema is None:
                schema = dict(annotation_keys=sorted(content), object_keys=sorted(objects[0]) if objects else [])
            counts = Counter(o['label'] for o in objects)
            labels.update(counts)
            image_counts.update(counts.keys())
            partial = content.get('is_fully_annotated') is False
            explicit_partial += partial
            wanted = sorted(label for label in counts if re.fullmatch(
                r'regulatory--maximum-speed-limit-(40|50|60|70|80)--g1', label))
            if key in splits['train'] and wanted and not partial:
                candidates.append(dict(image_key=key, annotation=member.filename,
                    source_split='train', proposed_labels=' | '.join(wanted),
                    all_labels=' | '.join(sorted(counts)), reviewed='no'))
    if not annotation_count:
        raise ValueError('No MTSD object annotations found; use the fully annotated annotation ZIP')
    mappings = [dict(source_label=label, target='Speed_limit_' + label.split('--')[1].split('-')[-1], reviewed='no')
                for label in sorted(labels) if re.fullmatch(r'regulatory--maximum-speed-limit-(40|50|60|70|80)--g1', label)]
    return dict(summary=dict(annotation_images=annotation_count, source_classes=len(labels),
        split_list_images={s: len(ids) for s, ids in splits.items()},
        explicitly_partial_images=explicit_partial, train_candidate_images=len(candidates),
        automatic_training_ready=False,
        limitation='Annotation-only scan: fully annotated archive provenance, unit/appearance, all CAR35 boxes, image integrity and exact/near holdout overlap still require review.'),
        class_counts=[dict(source_label=k, boxes=labels[k], images=image_counts[k]) for k in sorted(labels)],
        mapping_candidates=mappings, train_candidates=candidates, schema_example=schema)
