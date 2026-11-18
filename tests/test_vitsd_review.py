import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest


def fixture_zip(path):
    image = io.BytesIO()
    Image.new('RGB', (80, 40), 'red').save(image, format='PNG')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('ViTSD/data.yaml', 'names: [Speed_limit_60, Unreviewed_sign]\n')
        for split, name, label in [
            ('train', 'a', '0 .5 .5 .4 .4'),
            ('test', 'a_copy', '0 .5 .5 .4 .4'),
            ('val', 'conflict', '1 .5 .5 .4 .4'),
            ('train', 'invalid', '0 .99 .5 .4 .4'),
            ('train', 'empty', ''),
            ('train', 'missing', None),
        ]:
            # Different compression does not change the decoded appearance; exact
            # duplicates here intentionally exercise conflicting source labels.
            z.writestr(f'ViTSD/images/{split}/{name}.png', image.getvalue())
            if label is not None:
                z.writestr(f'ViTSD/labels/{split}/{name}.txt', label)
        z.writestr('ViTSD/images/train/broken.png', b'not an image')
        # The source also has COCO; selecting YOLO must not double the boxes.
        z.writestr('ViTSD/annotations.json', json.dumps(dict(
            images=[dict(id=1, file_name='images/train/a.png')],
            categories=[dict(id=0, name='Speed_limit_60')],
            annotations=[dict(id=1, image_id=1, category_id=0, bbox=[1, 1, 8, 8])],
        )))
    return path


def test_mount_zip_is_copied_once_with_progress_and_never_extracted(tmp_path):
    from training.data.vitsd_review import copy_zip_to_local
    source = fixture_zip(tmp_path / 'drive.zip')
    before = source.read_bytes()
    events = []
    target = copy_zip_to_local(source, tmp_path / 'local' / 'vitsd.zip', progress=events.append)
    assert target.read_bytes() == before and events[-1] == len(before)
    assert copy_zip_to_local(source, target) == target
    assert source.read_bytes() == before and not (tmp_path / 'local/ViTSD').exists()
    assert target.with_suffix('.zip.source.json').is_file()
    # A cached local copy must not silently accept corruption or another source.
    target.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='changed'):
        copy_zip_to_local(source, target)


def test_partial_audit_is_explicit_and_cache_is_bound_to_options(tmp_path):
    from training.data.vitsd_review import audit_zip
    source = fixture_zip(tmp_path / 'vitsd.zip')
    report = audit_zip(source, image_limit=2, cache_dir=tmp_path / 'cache')
    assert report['summary']['partial_scan'] and report['summary']['verify_decode']
    assert report['summary']['images_scanned'] == 2
    assert audit_zip(source, image_limit=2, cache_dir=tmp_path / 'cache') == report
    full = audit_zip(source, cache_dir=tmp_path / 'cache')
    assert not full['summary']['partial_scan']
    assert full['summary']['images_total'] == 7
    assert full['summary']['formats'] == {'yolo': 5}
    assert sum(r['boxes'] for r in full['images']) == 3


def test_review_quarantines_conflicts_and_never_calls_missing_labels_background(tmp_path):
    from training.data.vitsd_review import audit_zip, build_review
    report = audit_zip(fixture_zip(tmp_path / 'vitsd.zip'))
    digest = next(r['sha256'] for r in report['images'] if r['sha256'])
    review = build_review(report, reference={digest: ['train']})
    decisions = {Path(r['path']).stem: r for r in review['decisions']}
    assert decisions['missing']['decision'] == 'quarantine'
    assert decisions['invalid']['decision'] == 'quarantine'
    assert decisions['empty']['decision'] == 'quarantine'  # conflicting duplicate
    assert decisions['a']['decision'] == 'quarantine'
    assert review['duplicates'][0]['label_conflict'] is True
    assert review['duplicates'][0]['cross_split'] is True
    assert review['summary']['reference_exact_check'] == 'checked'
    assert review['summary']['reference_near_check'] == 'not_checked'
    assert review['summary']['training_ready'] is False
    mapping = {r['source_name']: r for r in review['mapping']}
    assert mapping['Speed_limit_60']['candidate_target_id'] == 2
    assert mapping['Unreviewed_sign']['candidate_target_id'] == ''
    assert all(r['approved'] is False for r in review['mapping'])


def test_review_without_reference_cannot_claim_cross_source_independence(tmp_path):
    from training.data.vitsd_review import audit_zip, build_review, write_review
    source = fixture_zip(tmp_path / 'vitsd.zip')
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = audit_zip(source)
    review = build_review(report)
    output = tmp_path / 'review'
    write_review(source, report, review, output, near_threshold=4, progress=None)
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['reference_exact_check'] == 'not_supplied'
    assert summary['independent_field_test'] is False
    assert (output / 'index.html').is_file()
    assert (output / 'mapping_candidates.csv').is_file()
    assert (output / 'quarantine.csv').is_file()
    assert (output / 'near_duplicate_edges.csv').is_file()
    assert (output / 'previews').is_dir()
    assert not (output / 'images/train').exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with pytest.raises(FileExistsError):
        write_review(source, report, review, output)


def test_archive_paths_and_duplicate_members_are_rejected(tmp_path):
    from training.data.vitsd_review import audit_zip
    for name in ['../outside.png', '/absolute.png']:
        path = tmp_path / 'unsafe.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr(name, b'x')
        with pytest.raises(ValueError, match='Unsafe'):
            audit_zip(path)


def test_reference_manifest_can_be_json_or_inside_zip_without_loading_images(tmp_path):
    from training.data.vitsd_review import load_reference
    digest = 'a' * 64
    value = dict(images=[dict(sha256=digest, split='train')])
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(value))
    assert load_reference(path) == {digest: ['train']}
    archive = tmp_path / 'reference.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('dataset/manifest.json', json.dumps(value))
    assert load_reference(archive) == {digest: ['train']}
    assert load_reference(None) is None
    path.write_text(json.dumps(dict(images=[dict(sha256=digest, split='unknown')])) )
    with pytest.raises(ValueError):
        load_reference(path)


def test_clean_empty_annotation_is_only_a_review_candidate(tmp_path):
    from training.data.vitsd_review import audit_zip, build_review
    archive = tmp_path / 'empty.zip'
    image = io.BytesIO(); Image.new('RGB', (30, 30)).save(image, format='PNG')
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('data.yaml', 'names: [Speed_limit_50]')
        z.writestr('images/train/a.png', image.getvalue())
        z.writestr('labels/train/a.txt', '')
    review = build_review(audit_zip(archive))
    assert review['decisions'][0]['decision'] == 'review_background'
    assert not review['summary']['training_ready']


def test_cache_tampering_and_post_audit_source_change_fail_explicitly(tmp_path):
    from training.data.vitsd_review import audit_zip, build_review, write_review
    source = fixture_zip(tmp_path/'vitsd.zip')
    report = audit_zip(source, cache_dir=tmp_path/'cache')
    cache = next((tmp_path/'cache').glob('*.json'))
    cache.write_text('{}')
    with pytest.raises(ValueError, match='cache changed'):
        audit_zip(source, cache_dir=tmp_path/'cache')
    with zipfile.ZipFile(source, 'a') as z:
        z.writestr('changed.txt', 'changed')
    with pytest.raises(ValueError, match='changed after audit'):
        write_review(source, report, build_review(report), tmp_path/'report')


def test_agreed_duplicates_are_reviewed_without_changing_original_splits(tmp_path):
    from training.data.vitsd_review import audit_zip, build_review
    source = tmp_path/'same.zip'
    image = io.BytesIO(); Image.new('RGB', (40, 40)).save(image, format='PNG')
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('data.yaml', 'names: [No_entry]')
        for split in ('train', 'test'):
            z.writestr(f'images/{split}/a.png', image.getvalue())
            z.writestr(f'labels/{split}/a.txt', '0 .5 .5 .2 .2')
    review = build_review(audit_zip(source))
    assert review['duplicates'][0]['label_conflict'] is False
    assert review['duplicates'][0]['cross_split'] is True
    assert {r['split'] for r in review['decisions']} == {'train', 'test'}
    assert {r['decision'] for r in review['decisions']} == {'review_car35'}
    assert review['summary']['training_ready'] is False


def test_duplicate_member_names_and_nested_zip_are_not_silently_audited(tmp_path):
    from training.data.vitsd_review import audit_zip
    source = tmp_path/'duplicate.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('data.yaml', 'names: [No_entry]')
        with pytest.warns(UserWarning, match='Duplicate'):
            z.writestr('data.yaml', 'names: [No_cars]')
    with pytest.raises(ValueError, match='duplicate'):
        audit_zip(source)
    source = tmp_path/'nested.zip'
    with zipfile.ZipFile(source, 'w') as z:
        z.writestr('inside.zip', b'not-expanded')
    with pytest.raises(ValueError, match='Unsupported archive'):
        audit_zip(source)
