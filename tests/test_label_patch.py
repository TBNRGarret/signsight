import json
from pathlib import Path

from PIL import Image
import pytest

from training.data.common import CAR35, digest_file


def dataset(tmp_path):
    root = tmp_path/'dataset'; root.mkdir()
    data = root/'image.png'; Image.new('RGB', (32, 32), 'blue').save(data)
    sha = digest_file(data)
    image = root/'images/train'/f'{sha}.png'; image.parent.mkdir(parents=True); data.rename(image)
    label = root/'labels/train'/f'{sha}.txt'; label.parent.mkdir(parents=True)
    label.write_bytes(b'2 0.5 0.5 0.2 0.2\r\n9 0.3 0.3 0.1 0.1\r\n')
    manifest = dict(kind='car35_folder_development_v4', names=CAR35,
                    images=[dict(sha256=sha, split='train', image=image.relative_to(root).as_posix(),
                                 label=label.relative_to(root).as_posix(), label_sha256=digest_file(label))])
    (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root, manifest, dict(image_sha256=sha, line_index=0, from_class=2, to_class=1,
                                reason='Original pixels clearly show 50', reviewed=True)


def test_patch_exports_only_reviewed_label_edits_and_preserves_source_bytes(tmp_path):
    from training.data.label_patch import create_label_patch
    root, manifest, edit = dataset(tmp_path)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    output = tmp_path/'patch'
    result = create_label_patch(root, output, [edit], expected_manifest_sha256=digest_file(root/'manifest.json'))
    row = manifest['images'][0]
    assert (output/row['label']).read_bytes() == before[Path(row['label'])].replace(b'2 ', b'1 ', 1)
    assert result['standalone_training_dataset'] is False
    assert result['source_manifest_sha256'] == digest_file(root/'manifest.json')
    assert result['changes'][0]['old_sha256'] == row['label_sha256']
    assert result['changes'][0]['new_sha256'] == digest_file(output/row['label'])
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    assert not (output/'images').exists()
    with pytest.raises(FileExistsError):
        create_label_patch(root, output, [edit], expected_manifest_sha256=digest_file(root/'manifest.json'))


@pytest.mark.parametrize('change', [dict(reviewed=False), dict(to_class=35), dict(to_class=True),
                                  dict(from_class=1), dict(line_index=-1), dict(reason=''),
                                  dict(image_sha256='../escape')])
def test_patch_rejects_unreviewed_invalid_or_stale_edits(tmp_path, change):
    from training.data.label_patch import create_label_patch
    root, _, edit = dataset(tmp_path); edit.update(change)
    with pytest.raises(ValueError):
        create_label_patch(root, tmp_path/'patch', [edit], expected_manifest_sha256=digest_file(root/'manifest.json'))
    assert not (tmp_path/'patch').exists()


def test_patch_rejects_changed_manifest_labels_images_and_source_overwrite(tmp_path):
    from training.data.label_patch import create_label_patch
    root, m, edit = dataset(tmp_path)
    expected = digest_file(root/'manifest.json')
    with pytest.raises(ValueError, match='manifest'):
        create_label_patch(root, tmp_path/'patch', [edit], expected_manifest_sha256='0'*64)
    with pytest.raises(ValueError, match='outside'):
        create_label_patch(root, root/'patch', [edit], expected_manifest_sha256=expected)
    with pytest.raises(ValueError, match='Duplicate'):
        create_label_patch(root, tmp_path/'patch', [edit, edit], expected_manifest_sha256=expected)
    label = root/m['images'][0]['label']; raw = label.read_bytes(); label.write_bytes(raw+b'\n')
    with pytest.raises(ValueError, match='label changed'):
        create_label_patch(root, tmp_path/'patch', [edit], expected_manifest_sha256=expected)
    label.write_bytes(raw)
    (root/m['images'][0]['image']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='image changed'):
        create_label_patch(root, tmp_path/'patch', [edit], expected_manifest_sha256=expected)


def test_patch_removes_reviewed_duplicate_only_when_a_matching_retained_box_exists(tmp_path):
    from training.data.label_patch import create_label_patch
    root, m, edit = dataset(tmp_path)
    row = m['images'][0]; label = root/row['label']
    label.write_bytes(b'2 .5 .5 .2 .2\r\n4 .5 .5 .2 .2\r\n9 .3 .3 .1 .1\r\n')
    m['images'][0]['label_sha256'] = digest_file(label)
    (root/'manifest.json').write_text(json.dumps(m))
    edit.update(action='remove_duplicate', to_class=4, retained_line_index=1,
                reason='Same physical sign has an existing correct class 80 box; remove contradictory duplicate 60.')
    before = label.read_bytes()
    result = create_label_patch(root, tmp_path/'patch', [edit],
                                expected_manifest_sha256=digest_file(root/'manifest.json'))
    assert (tmp_path/'patch'/row['label']).read_bytes() == b'4 .5 .5 .2 .2\r\n9 .3 .3 .1 .1\r\n'
    assert label.read_bytes() == before
    assert result['removed_boxes'] == 1
    assert result['relabeled_boxes'] == 0


@pytest.mark.parametrize('retained_index', [0, 1, -1])
def test_duplicate_removal_cannot_drop_the_only_box_or_point_at_an_unrelated_box(tmp_path, retained_index):
    from training.data.label_patch import create_label_patch
    root, _, edit = dataset(tmp_path)
    edit.update(action='remove_duplicate', to_class=9, retained_line_index=retained_index)
    with pytest.raises(ValueError):
        create_label_patch(root, tmp_path/'patch', [edit],
                           expected_manifest_sha256=digest_file(root/'manifest.json'))
