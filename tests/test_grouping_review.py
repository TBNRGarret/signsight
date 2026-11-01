"""Grouping evidence uses synthetic images and never a personal runtime dataset."""
import importlib.util
import csv
import hashlib
import json

import pytest


def review_module():
    assert importlib.util.find_spec('training.data.grouping_review'), 'Missing grouping review feature'
    from training.data import grouping_review
    return grouping_review


def record(index, value, group='same', split='train', alias=None):
    path = alias or f'source/images/unique{index}.png'
    return dict(sha256=str(index), source_path=path, aliases=[path],
                visual_hash=value, group=group, split=split)


def test_dhash_chain_explains_transitive_membership_with_direct_distances():
    rows = [record(0, 0), record(1, 1), record(2, 3),
            record(3, 2**32-1, group='other', split='val')]
    result = review_module().explain_grouping(rows, block_size=1, near_threshold=1)
    assert result['partition_matches'] is True
    assert [(e['left'], e['right'], e['reason'], e['distance']) for e in result['edges']] == [
        ('1', '0', 'dhash', 1), ('2', '1', 'dhash', 1)]
    assert result['components'][0] == result['components'][2]
    assert result['components'][3] != result['components'][0]
    assert rows[0]['group'] == 'same'  # Replay never rewrites stored groups/splits.


def test_filename_edge_exposes_namespace_collision_across_directories():
    rows = [record(0, 0, alias='camera_a/images/frame100.png'),
            record(1, 255, alias='camera_b/images/frame101.png')]
    result = review_module().explain_grouping(rows, block_size=100, near_threshold=None)
    assert result['partition_matches'] is True
    assert len(result['edges']) == 1
    edge = result['edges'][0]
    assert edge['reason'] == 'filename'
    assert edge['namespace_collision'] is True
    assert {edge['left_alias'], edge['right_alias']} == {
        'camera_a/images/frame100.png', 'camera_b/images/frame101.png'}


def test_explicit_capture_metadata_replaces_filename_heuristic():
    rows = [record(0, 0, alias='x/frame100.png'), record(1, 3, alias='x/frame101.png'),
            record(2, 7, group='other', alias='x/frame102.png')]
    groups = {'x/frame100.png': 'trip_a', 'x/frame101.png': 'trip_a', 'x/frame102.png': 'trip_b'}
    result = review_module().explain_grouping(rows, groups=groups, near_threshold=None)
    assert result['partition_matches'] is True
    assert [edge['reason'] for edge in result['edges']] == ['capture']
    assert result['edges'][0]['key'] == 'trip_a'
    with pytest.raises(ValueError, match='capture group'):
        review_module().explain_grouping(rows, groups={}, near_threshold=None)


def test_dense_identical_hashes_export_a_forest_instead_of_all_pairs():
    rows = [record(i, 0) for i in range(400)]
    result = review_module().explain_grouping(rows, block_size=1, near_threshold=0)
    assert len(result['edges']) == 399
    assert result['partition_matches'] is True


def test_replay_marks_partition_disagreement_and_cross_split_links():
    rows = [record(0, 0, group='a'), record(1, 1, group='b', split='test')]
    result = review_module().explain_grouping(rows, block_size=1, near_threshold=1)
    assert result['partition_matches'] is False
    assert result['edges'][0]['cross_split'] is True


def test_replay_agrees_with_preparation_for_mixed_alias_and_hash_links():
    import random
    from training.data.supsign import cluster_records
    rng = random.Random(7)
    rows = [record(i, rng.getrandbits(12), alias=f'{i%3}/frame{i}.png') for i in range(90)]
    rows[10]['aliases'].append('other/frame70.png')
    for row, group in zip(rows, cluster_records(rows, block_size=3, near_threshold=1)):
        row['group'] = group
    result = review_module().explain_grouping(rows, block_size=3, near_threshold=1)
    assert result['partition_matches'] is True
    assert len(result['edges']) == len(rows)-len(set(result['components']))


def prepared_review_fixture(tmp_path):
    from test_supsign_training import archive_fixture
    from training.data.supsign import prepare_supsign
    negative = '2 .5 .5 .4 .4\n'
    source = archive_fixture(tmp_path, {'train/labels/photo_0.txt': negative,
                                      'test/labels/copy.txt': negative})
    root = tmp_path/'dataset'
    manifest = prepare_supsign(source, root, classes=['No_entry', 'No_parking'],
                               block_size=2, near_threshold=None)
    return root, manifest


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def test_report_exports_complete_tables_and_bounded_previews_without_mutation(tmp_path):
    root, manifest = prepared_review_fixture(tmp_path)
    before = {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*') if p.is_file()}
    output = tmp_path/'review'
    module = review_module()
    assert hasattr(module, 'write_grouping_review'), 'Missing grouping report export'
    summary = module.write_grouping_review(root, output, max_groups=2, samples_per_group=2)
    assert summary['images'] == 18 and summary['groups'] == 9
    assert summary['partition_matches'] is True
    assert summary['independent_field_test'] is False
    assert summary['manifest_sha256'] == before[next(p for p in before if p.name == 'manifest.json')]
    assert summary['edge_count'] == 9
    assert sum(s['images'] for s in summary['splits'].values()) == 18
    assert sum(s['groups'] for s in summary['splits'].values()) == 9
    assert len(csv_rows(output/'groups.csv')) == 9
    membership = csv_rows(output/'group_members.csv')
    assert len(membership) == 18
    assert sum(len(json.loads(r['aliases'])) for r in membership) == 19
    assert len(csv_rows(output/'grouping_edges.csv')) == 9
    coverage = csv_rows(output/'class_coverage.csv')
    assert len(coverage) == 6  # Both classes, including zero counts, in all three splits.
    assert sum(int(r['boxes']) for r in coverage if r['name'] == 'No_entry') == 17
    assert sum(int(r['images']) for r in coverage if r['name'] == 'No_entry') == 17
    assert sum(int(r['negative_images']) for r in csv_rows(output/'groups.csv')) == 1
    preview_groups = json.loads((output/'grouping_summary.json').read_text())['previews']
    assert len(preview_groups) == 2
    assert all(len(p['images']) <= 2 for p in preview_groups)
    assert all((output/p['contact_sheet']).is_file() for p in preview_groups)
    assert (output/'index.html').is_file()
    assert before == {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.rglob('*') if p.is_file()}
    # Existing output is preserved rather than mixed with a previous report.
    with pytest.raises(FileExistsError):
        module.write_grouping_review(root, output)


@pytest.mark.parametrize('target', ['inside', 'ancestor'])
def test_report_rejects_output_that_overlaps_dataset(tmp_path, target):
    root, _ = prepared_review_fixture(tmp_path)
    module = review_module()
    assert hasattr(module, 'write_grouping_review'), 'Missing grouping report export'
    output = root/'report' if target == 'inside' else root.parent
    with pytest.raises(ValueError, match='outside'):
        module.write_grouping_review(root, output)


def test_report_rejects_tampering_before_publishing_partial_results(tmp_path):
    root, manifest = prepared_review_fixture(tmp_path)
    (root/manifest['images'][0]['label']).write_text('0 .5 .5 .1 .1\n')
    module = review_module()
    assert hasattr(module, 'write_grouping_review'), 'Missing grouping report export'
    with pytest.raises(ValueError, match='changed'):
        module.write_grouping_review(root, tmp_path/'review')
    assert not (tmp_path/'review').exists()


def test_report_escapes_source_metadata_in_html(tmp_path):
    root, manifest = prepared_review_fixture(tmp_path)
    manifest['images'][0]['source_path'] = '<script>alert("unsafe")</script>'
    (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    module = review_module()
    assert hasattr(module, 'write_grouping_review'), 'Missing grouping report export'
    module.write_grouping_review(root, tmp_path/'review', max_groups=9)
    page = (tmp_path/'review/index.html').read_text(encoding='utf-8')
    assert '<script>' not in page
    assert '&lt;script&gt;' in page
    assert 'https://' not in page  # Offline review assets.


def test_capture_cache_without_original_csv_marks_evidence_incomplete(tmp_path):
    from test_supsign_training import archive_fixture
    from training.data.supsign import prepare_supsign
    source = archive_fixture(tmp_path)
    groups = {f'{("train", "valid", "test")[i%3]}/images/photo_{i}.png': f'trip{i//3}' for i in range(18)}
    groups['test/images/copy.png'] = 'trip0'
    root = tmp_path/'dataset'
    prepare_supsign(source, root, classes=['No_entry'], groups=groups, near_threshold=None)
    module = review_module()
    assert hasattr(module, 'write_grouping_review'), 'Missing grouping report export'
    summary = module.write_grouping_review(root, tmp_path/'review')
    assert summary['partition_matches'] is None
    assert summary['evidence_complete'] is False
    assert 'capture_metadata_unavailable' in summary['warnings']
    assert csv_rows(tmp_path/'review/grouping_edges.csv') == []
    complete = module.write_grouping_review(root, tmp_path/'with-csv', groups=groups)
    assert complete['partition_matches'] is True and complete['evidence_complete'] is True
    assert {e['reason'] for e in csv_rows(tmp_path/'with-csv/grouping_edges.csv')} == {'capture'}
    changed = dict(groups, **{'test/images/copy.png': 'different_trip'})
    with pytest.raises(ValueError, match='capture metadata'):
        module.write_grouping_review(root, tmp_path/'wrong-csv', groups=changed)


def test_preview_selection_is_bounded_for_a_large_single_reason_group(tmp_path):
    """Selecting three preview edges must not compare every edge to all others."""
    from training.data.grouping_render import render_review
    root, manifest = prepared_review_fixture(tmp_path)
    comparisons = []

    class MeasuredEdge(dict):
        def __eq__(self, other):
            comparisons.append(1)
            return super().__eq__(other)

    # A valid forest of distinct edges with the same reason, as in a giant
    # dHash component. Image files are real fixture files, not renderer mocks.
    rows = [dict(r, group='joined', split='train', classes=['No_entry']) for r in manifest['images']]
    edges = [MeasuredEdge(left=r['sha256'], right=rows[0]['sha256'], left_group='joined',
                          right_group='joined', reason='dhash', distance=1, key='',
                          left_alias=r['source_path'], right_alias=rows[0]['source_path'],
                          cross_split=False, namespace_collision=False) for r in rows[1:]]
    stats = dict(group='joined', split='train', images=18, boxes=34, negative_images=1, source_namespaces=3)
    summary = dict(images=18, groups=1, edge_count=17, partition_matches=True, limitations='Replay only',
                   warnings=[], manifest_sha256='fixture', splits={})
    output = tmp_path/'render'; output.mkdir()
    inventory = render_review(root, output, summary, [stats], [], {'joined': rows}, edges, 1, 2)
    assert len(inventory[0]['edge_examples']) == 3
    assert len(comparisons) <= 3*len(edges)
