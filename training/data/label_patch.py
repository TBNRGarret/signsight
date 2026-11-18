"""Export small, reviewed CAR35 label overlays; never mutate the source dataset."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import tempfile

from training.data.common import CAR35, digest_file, write_json


def create_label_patch(root, output, edits, *, expected_manifest_sha256):
    """Hash-bound label replacements, without images or a standalone training YAML.

    line_index refers to a physical, zero-based source label line. Only its class
    token changes; bounding-box text, whitespace, line endings and other labels
    remain intact. An applying tool must create a new dataset identity and verify
    the source hashes; copying these labels into V4 in place is not supported.
    """
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Patch output must be outside the source dataset')
    if output.exists():
        raise FileExistsError(output)
    manifest_file = root/'manifest.json'
    if (not re.fullmatch('[a-f0-9]{64}', expected_manifest_sha256 or '') or
            digest_file(manifest_file) != expected_manifest_sha256):
        raise ValueError('Source manifest changed or checksum is invalid')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('kind') != 'car35_folder_development_v4' or manifest.get('names') != CAR35:
        raise ValueError('Expected the original CAR35 V4 manifest and class order')
    rows = {r['sha256']: r for r in manifest['images']}
    if len(rows) != len(manifest['images']):
        raise ValueError('Duplicate source image identity')
    if not edits:
        raise ValueError('Supply at least one reviewed edit')
    grouped, seen = defaultdict(list), set()
    for edit in edits:
        sha, index = edit.get('image_sha256', ''), edit.get('line_index')
        before, after = edit.get('from_class'), edit.get('to_class')
        if (not re.fullmatch('[a-f0-9]{64}', sha) or sha not in rows or
                type(index) is not int or index < 0 or edit.get('reviewed') is not True or
                any(type(c) is not int or not 0 <= c < 35 for c in (before, after)) or before == after or
                not isinstance(edit.get('reason'), str) or not edit['reason'].strip()):
            raise ValueError('Invalid, unreviewed or unsupported CAR35 edit')
        if (sha, index) in seen:
            raise ValueError('Duplicate edit for one label line')
        seen.add((sha, index)); grouped[sha].append(dict(edit))
    changed, content_by_path = [], {}
    for sha, changes in sorted(grouped.items()):
        row = rows[sha]; split = row['split']
        if split not in ('train', 'val', 'test'):
            raise ValueError('Invalid source split')
        image, label = root/row['image'], root/row['label']
        if (image.parent != root/'images'/split or image.stem != sha or
                row['label'] != f'labels/{split}/{sha}.txt' or
                not image.resolve().is_relative_to(root) or not label.resolve().is_relative_to(root)):
            raise ValueError('Unsafe source image/label path')
        raw = label.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['label_sha256']:
            raise ValueError('Source label changed')
        if digest_file(image) != sha:
            raise ValueError('Source image changed')
        lines = raw.decode('utf-8').splitlines(keepends=True)
        for edit in changes:
            index = edit['line_index']
            if index >= len(lines):
                raise ValueError('Label line no longer exists')
            fields = lines[index].split()
            if len(fields) != 5 or fields[0] != str(edit['from_class']):
                raise ValueError('Source class/label line differs from reviewed edit')
            x, y, w, h = map(float, fields[1:])
            if (not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0 or
                    min(x-w/2, y-h/2) < -1e-6 or max(x+w/2, y+h/2) > 1+1e-6):
                raise ValueError('Source bbox requires separate review')
            lines[index] = re.sub(r'^(\s*)\d+', lambda m: m[1]+str(edit['to_class']), lines[index], count=1)
        updated = ''.join(lines).encode('utf-8')
        content_by_path[row['label']] = updated
        changed.append(dict(image_sha256=sha, split=split, label=row['label'],
                            old_sha256=row['label_sha256'], new_sha256=hashlib.sha256(updated).hexdigest(),
                            edits=changes))
    result = dict(schema_version=1, kind='car35_reviewed_label_patch', source_manifest_sha256=expected_manifest_sha256,
                  names=list(CAR35), changed_images=len(changed), changed_boxes=len(edits), changes=changed,
                  standalone_training_dataset=False, independent_field_test=False,
                  source_modified=False, split_changed=False,
                  usage='Review overlay only. Materialize a separately identified dataset on a writable copy before training; '
                        'preserve the original V4 ZIP/directory and update manifest hashes/counts. Never apply into V4 in place.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.label-patch-', dir=output.parent) as temporary:
        stage = Path(temporary)/'patch'; stage.mkdir()
        for relative, content in content_by_path.items():
            target = stage/PurePosixPath(relative); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        write_json(stage/'patch.json', result)
        with (stage/'corrections.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            fields = ['image_sha256', 'split', 'line_index', 'from_class', 'from_name', 'to_class', 'to_name', 'reason']
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
            for row in changed:
                for edit in row['edits']:
                    writer.writerow(dict(image_sha256=row['image_sha256'], split=row['split'],
                                         line_index=edit['line_index'], from_class=edit['from_class'],
                                         from_name=CAR35[edit['from_class']], to_class=edit['to_class'],
                                         to_name=CAR35[edit['to_class']], reason=edit['reason']))
        (stage/'README.md').write_text('# CAR35 reviewed label overlay\n\n'+result['usage']+'\n', encoding='utf-8')
        if output.exists():
            raise FileExistsError(output)
        stage.rename(output)
    return result
