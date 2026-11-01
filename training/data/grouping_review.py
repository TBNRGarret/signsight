"""Read-only grouping diagnostics; never changes preparation or split decisions.

Edges are a replayed spanning forest, not an exhaustive similarity graph or a
record of the historical preparation process. Keep replay parity tests against
cluster_records when changing either implementation.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile

from PIL import Image

from training.data.cache import verify_dataset
from training.data.common import SPLITS, read_json, write_json
from training.data.supsign import visual_hash


def explain_grouping(rows, *, block_size=100, near_threshold=4, groups=None):
    """Replay the current grouping rules, retaining only component-joining edges."""
    if block_size < 1 or (near_threshold is not None and not 0 <= near_threshold <= 8):
        raise ValueError('Invalid grouping settings')
    parent = list(range(len(rows)))
    edges, seen = [], {}
    tree = None

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def join(left, right, reason, *, key='', distance=None, left_alias='', right_alias=''):
        a, b = find(left), find(right)
        if a == b:
            return
        parent[max(a, b)] = min(a, b)
        lrow, rrow = rows[left], rows[right]
        edges.append(dict(left=lrow['sha256'], right=rrow['sha256'], reason=reason,
                          key=key, distance=distance, left_alias=left_alias, right_alias=right_alias,
                          left_group=lrow['group'], right_group=rrow['group'],
                          cross_split=lrow['split'] != rrow['split'],
                          namespace_collision=reason == 'filename' and
                          PurePosixPath(left_alias).parent != PurePosixPath(right_alias).parent))

    for index, row in enumerate(rows):
        for alias in row['aliases']:
            relative = alias.split('!/', 1)[-1]
            if groups is not None:
                capture = groups.get(relative, groups.get(alias))
                if not isinstance(capture, str) or not capture.strip():
                    raise ValueError(f'Missing capture group: {relative}')
                key, reason, description = ('capture', capture.strip()), 'capture', capture.strip()
            else:
                match = re.fullmatch(r'(.*?)([0-9]+)', PurePosixPath(relative).stem)
                key = ('filename', match[1], int(match[2]) // block_size) if match else ('image', row['sha256'])
                reason, description = 'filename', str(key[1:])
            if key in seen:
                representative, previous = seen[key]
                join(index, representative, reason, key=description,
                     left_alias=relative, right_alias=previous)
            else:
                seen[key] = index, relative
        if near_threshold is None:
            continue
        value = row['visual_hash']
        if tree is None:
            tree = value, index, {}
            continue
        # Same BK-tree traversal as preparation; no pairwise hash matrix.
        pending = [tree]
        while pending:
            other, representative, children = pending.pop()
            distance = (value ^ other).bit_count()
            if distance <= near_threshold:
                join(index, representative, 'dhash', distance=distance,
                     left_alias=row['source_path'], right_alias=rows[representative]['source_path'])
            pending.extend(child for edge, child in children.items()
                           if distance-near_threshold <= edge <= distance+near_threshold)
        node = tree
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0:
                break
            if distance not in node[2]:
                node[2][distance] = value, index, {}
                break
            node = node[2][distance]

    components = [find(i) for i in range(len(rows))]
    stored_to_replayed, replayed_to_stored = defaultdict(set), defaultdict(set)
    for row, component in zip(rows, components):
        stored_to_replayed[row['group']].add(component)
        replayed_to_stored[component].add(row['group'])
    matches = all(len(values) == 1 for values in
                  [*stored_to_replayed.values(), *replayed_to_stored.values()])
    return dict(edges=edges, components=components, partition_matches=matches)


def write_grouping_review(root, output, *, groups=None, max_groups=12,
                          samples_per_group=6, progress=None):
    """Verify a prepared cache and publish a bounded, offline review outside it.

    Explicit capture groups cannot be recovered from their manifest digest. When
    their CSV is unavailable, only dHash evidence is replayed, and agreement is
    deliberately unknown. Report files never become part of the dataset cache.
    """
    from training.data.grouping_render import render_review, write_csv

    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Grouping report must be outside the dataset')
    if output.exists():
        raise FileExistsError(output)
    if (type(max_groups) is not int or not 1 <= max_groups <= 50 or
            type(samples_per_group) is not int or not 1 <= samples_per_group <= 12):
        raise ValueError('Preview limits: 1..50 groups and 1..12 images per group')
    manifest = read_json(root/'manifest.json')
    # Resolve before the existing hash verifier, including symlinked files.
    for row in manifest['images']:
        for key in ('image', 'label'):
            if not (root/row[key]).resolve().is_relative_to(root):
                raise ValueError('Dataset file resolves outside dataset')
    identity = verify_dataset(root)
    settings = manifest['recipe']
    supplied = manifest['split_provenance'] == 'provided_capture_groups'
    if groups is not None:
        digest = hashlib.sha256(json.dumps(groups, sort_keys=True).encode()).hexdigest()
        if not supplied or digest != settings['groups_sha256']:
            raise ValueError('Provided capture metadata differs from the preparation recipe')
    evidence_complete = not supplied or groups is not None
    rows = [dict(row) for row in manifest['images']]
    coverage = {(i, split): dict(class_id=i, name=name, split=split, boxes=0, images=0, groups=set())
                for i, name in enumerate(manifest['names']) for split in SPLITS}
    members, group_counts = defaultdict(list), {}
    processing = progress(rows, desc='Review labels / visual hashes', unit='image') if progress else rows
    for row in processing:
        counts = Counter(int(line.split()[0]) for line in
                         (root/row['label']).read_text(encoding='utf-8').splitlines() if line.strip())
        if any(i < 0 or i >= len(manifest['names']) for i in counts):
            raise ValueError('Label class outside dataset taxonomy')
        row['classes'] = [manifest['names'][i] for i in sorted(counts)]
        group = row['group']
        members[group].append(row)
        stats = group_counts.setdefault(group, dict(group=group, split=row['split'], images=0,
                                                   boxes=0, negative_images=0, namespaces=set()))
        stats['images'] += 1
        stats['boxes'] += sum(counts.values())
        stats['negative_images'] += not counts
        stats['namespaces'].update(str(PurePosixPath(a.split('!/', 1)[-1]).parent) for a in row['aliases'])
        for cls, count in counts.items():
            value = coverage[cls, row['split']]
            value['boxes'] += count
            value['images'] += 1
            value['groups'].add(group)
        if settings['near_threshold'] is not None:
            with Image.open(root/row['image']) as image:
                row['visual_hash'] = visual_hash(image)
        else:
            row['visual_hash'] = 0
    if evidence_complete:
        replay = explain_grouping(rows, block_size=settings['block_size'],
                                  near_threshold=settings['near_threshold'], groups=groups)
    else:
        # Empty aliases disable filename matching; do not invent explicit groups.
        replay = explain_grouping([dict(row, aliases=[]) for row in rows],
                                  near_threshold=settings['near_threshold'])
        replay['partition_matches'] = None

    group_rows = sorted(group_counts.values(), key=lambda r: (-r['images'], r['group']))
    for row in group_rows:
        row['source_namespaces'] = len(row.pop('namespaces'))
    coverage_rows = [dict(value, groups=len(value['groups'])) for value in coverage.values()]
    split_stats = {}
    warnings = []
    for split in SPLITS:
        values = [r for r in group_rows if r['split'] == split]
        images = sum(r['images'] for r in values)
        largest = max((r['images'] for r in values), default=0)
        split_stats[split] = dict(images=images, groups=len(values), largest_group_images=largest,
                                  largest_group_fraction=largest/images if images else 0)
        if len(values) < 5:
            warnings.append(f'few_groups:{split}')
        if images and largest/images > .5:
            warnings.append(f'dominant_group:{split}')
    if not evidence_complete:
        warnings.append('capture_metadata_unavailable')
    if replay['partition_matches'] is False:
        warnings.append('replay_partition_mismatch')
    if any(edge['cross_split'] for edge in replay['edges']):
        warnings.append('replayed_cross_split_link')
    if any(edge['namespace_collision'] for edge in replay['edges']):
        warnings.append('filename_namespace_collision')
    summary = dict(schema_version=1, images=len(rows), groups=len(group_rows), splits=split_stats,
                   manifest_sha256=identity['manifest_sha256'],
                   dataset_content_sha256=identity['dataset_content_sha256'], recipe=settings,
                   split_provenance=manifest['split_provenance'], independent_field_test=False,
                   evidence_complete=evidence_complete, partition_matches=replay['partition_matches'],
                   edge_count=len(replay['edges']), edge_reasons=dict(Counter(e['reason'] for e in replay['edges'])),
                   warnings=warnings, previews=[],
                   limitations='Replayed spanning forest, not all similarity edges or a historical trace. '
                               'Filename/dHash links do not prove independent trips or physical signs. '
                               'Few/dominant groups are review flags, not proof of leakage. '
                               'Preview samples are spread by source filename, not statistically representative.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.grouping-review-', dir=output.parent) as temporary:
        stage = Path(temporary)/'report'
        stage.mkdir()
        write_csv(stage/'groups.csv', group_rows, ['group', 'split', 'images', 'boxes', 'negative_images', 'source_namespaces'])
        write_csv(stage/'class_coverage.csv', coverage_rows, ['class_id', 'name', 'split', 'boxes', 'images', 'groups'])
        membership = [dict(sha256=r['sha256'], image=r['image'], group=r['group'], split=r['split'],
                           source_path=r['source_path'], aliases=json.dumps(r['aliases'], ensure_ascii=False),
                           classes=json.dumps(r['classes'], ensure_ascii=False)) for r in rows]
        write_csv(stage/'group_members.csv', membership,
                  ['sha256', 'image', 'group', 'split', 'source_path', 'aliases', 'classes'])
        write_csv(stage/'grouping_edges.csv', replay['edges'],
                  ['left', 'right', 'reason', 'key', 'distance', 'left_alias', 'right_alias',
                   'left_group', 'right_group', 'cross_split', 'namespace_collision'])
        summary['previews'] = render_review(root, stage, summary, group_rows, coverage_rows,
                                            members, replay['edges'], max_groups, samples_per_group)
        write_json(stage/'grouping_summary.json', summary)
        stage.rename(output)
    return summary
