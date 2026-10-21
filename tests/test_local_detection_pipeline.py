import csv
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.local_detection_pipeline import (
    inspect_sources, prepare_dataset, split_groups, verify_prepared, run_model,
)


def fixture(root):
    for index, split in enumerate(('train', 'val', 'test')):
        image = root / f'images/{split}/sign.png'
        image.parent.mkdir(parents=True)
        Image.new('RGB', (40, 30), (index * 70, 30, 10)).save(image)
        label = root / f'labels/{split}/sign.txt'
        label.parent.mkdir(parents=True)
        label.write_text('0 0.5 0.5 0.4 0.2\n')
    (root / 'data.yaml').write_text('names: [P.102]\n')


def reviewed_plan(tmp_path):
    raw = tmp_path / 'raw'
    fixture(raw)
    report = tmp_path / 'eda'
    inspect_sources({'sample': str(raw)}, report)
    plan = json.loads((report / 'plan.json').read_text())
    plan.update(reviewed=True, split_reviewed=True)
    (report / 'plan.json').write_text(json.dumps(plan))
    return report / 'plan.json'


def test_eda_is_readonly_and_prepare_requires_explicit_review(tmp_path):
    plan = reviewed_plan(tmp_path)
    value = json.loads(plan.read_text()); value['reviewed'] = False
    plan.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='reviewed'):
        prepare_dataset(plan, tmp_path / 'prepared')
    assert not (tmp_path / 'prepared').exists()
    assert (tmp_path / 'raw/labels/train/sign.txt').read_text() == '0 0.5 0.5 0.4 0.2\n'


def test_roundtrip_prepare_preserves_boxes_and_detects_tampering(tmp_path):
    plan = reviewed_plan(tmp_path)
    output = tmp_path / 'prepared'
    prepare_dataset(plan, output)
    result = verify_prepared(output / 'data.yaml')
    assert result['images'] == 3
    assert result['names'] == ['P.102']
    labels = list((output / 'labels/train').glob('*.txt'))
    assert labels[0].read_text().split() == ['0', '0.5000000000', '0.5000000000', '0.4000000000', '0.2000000000']
    labels[0].write_text('0 0.5 0.5 0.1 0.1\n')
    with pytest.raises(ValueError, match='changed'):
        verify_prepared(output / 'data.yaml')


@pytest.mark.parametrize('problem', ['leak', 'missing', 'invalid', 'empty', 'mapping', 'crowd'])
def test_prepare_rejects_unsafe_inputs_without_publishing_partial_dataset(tmp_path, problem):
    plan = reviewed_plan(tmp_path)
    raw = tmp_path / 'raw'
    if problem == 'leak':
        (raw / 'images/test/sign.png').write_bytes((raw / 'images/train/sign.png').read_bytes())
    elif problem == 'missing':
        (raw / 'labels/train/sign.txt').unlink()
    elif problem == 'invalid':
        (raw / 'labels/train/sign.txt').write_text('0 0.99 0.5 0.4 0.2')
    elif problem == 'empty':
        (raw / 'labels/train/sign.txt').write_text('')
    elif problem == 'mapping':
        value = json.loads(plan.read_text()); value['class_map'][0]['target'] = None
        plan.write_text(json.dumps(value))
    else:
        (raw / 'labels/train/sign.txt').unlink()
        (raw / 'annotations.json').write_text(json.dumps({
            'images': [{'id': 1, 'file_name': 'images/train/sign.png', 'width': 40, 'height': 30}],
            'categories': [{'id': 0, 'name': 'P.102'}],
            'annotations': [{'image_id': 1, 'category_id': 0, 'bbox': [10, 10, 5, 5], 'iscrowd': 1}],
        }))
    with pytest.raises(ValueError):
        prepare_dataset(plan, tmp_path / 'prepared')
    assert not (tmp_path / 'prepared').exists()


def test_group_leaks_and_output_inside_raw_are_rejected(tmp_path):
    plan = reviewed_plan(tmp_path)
    assignment = plan.parent / 'assignments.csv'
    rows = list(csv.DictReader(assignment.open(newline='', encoding='utf-8')))
    for row in rows:
        row['group'] = 'same-recording'
    with assignment.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError, match='group'):
        prepare_dataset(plan, tmp_path / 'prepared')
    with pytest.raises(ValueError, match='source'):
        prepare_dataset(plan, tmp_path / 'raw/prepared')


def test_group_split_is_deterministic_keeps_frames_together_and_requires_groups():
    rows = [{'dataset': 'x', 'path': str(i), 'group': str(i // 2), 'split': 'unknown', 'exclude_reason': ''}
            for i in range(20)]
    first = split_groups(rows, seed=42)
    assert first == split_groups(rows, seed=42)
    assert all(first[i]['split'] == first[i+1]['split'] for i in range(0, 20, 2))
    assert {r['split'] for r in first} == {'train', 'val', 'test'}
    assert rows[0]['split'] == 'unknown'
    rows[0]['group'] = ''
    with pytest.raises(ValueError, match='group'):
        split_groups(rows)


def test_prepared_output_cannot_overwrite_existing_directory(tmp_path):
    plan = reviewed_plan(tmp_path)
    output = tmp_path / 'prepared'; output.mkdir()
    marker = output / 'keep.txt'; marker.write_text('keep')
    with pytest.raises(FileExistsError):
        prepare_dataset(plan, output)
    assert marker.read_text() == 'keep'


def test_explicit_annotation_choice_is_saved_in_plan_and_used_when_preparing(tmp_path):
    raw = tmp_path / 'raw'; fixture(raw)
    (raw / 'annotations.json').write_text(json.dumps({
        'images': [{'id': 1, 'file_name': 'images/train/sign.png', 'width': 40, 'height': 30}],
        'categories': [{'id': 7, 'name': 'other_export_class'}],
        'annotations': [{'image_id': 1, 'category_id': 7, 'bbox': [10, 10, 5, 5]}],
    }))
    eda = tmp_path / 'eda'
    inspect_sources({'sample': str(raw)}, eda, annotation_format='yolo')
    plan_path = eda / 'plan.json'; plan = json.loads(plan_path.read_text())
    assert plan['annotation_format'] == 'yolo' and plan['names'] == ['P.102']
    plan.update(reviewed=True, split_reviewed=True); plan_path.write_text(json.dumps(plan))
    manifest = prepare_dataset(plan_path, tmp_path / 'prepared')
    assert manifest['annotation_format'] == 'yolo'
    assert verify_prepared(tmp_path / 'prepared/data.yaml')['images'] == 3


def test_prepare_rejects_classes_present_only_in_validation_or_test(tmp_path):
    plan_path = reviewed_plan(tmp_path)
    (tmp_path / 'raw/data.yaml').write_text('names: [P.102, W.227]\n')
    (tmp_path / 'raw/labels/test/sign.txt').write_text('1 0.5 0.5 0.4 0.2\n')
    # Re-audit the new mapping before reviewing it, as a user would.
    fresh = tmp_path / 'eda_new'
    inspect_sources({'sample': str(tmp_path / 'raw')}, fresh)
    plan_path = fresh / 'plan.json'
    plan = json.loads(plan_path.read_text()); plan.update(reviewed=True, split_reviewed=True)
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='train.*W.227'):
        prepare_dataset(plan_path, tmp_path / 'prepared')
    assert not (tmp_path / 'prepared').exists()


def test_zip_images_are_copied_without_extracting_source_and_mapping_changes_are_rejected(tmp_path):
    import zipfile

    original = tmp_path / 'original'; fixture(original)
    zipped = tmp_path / 'zipped'; zipped.mkdir()
    with zipfile.ZipFile(zipped / 'sample.zip', 'w') as archive:
        for path in original.rglob('*'):
            if path.is_file():
                archive.write(path, path.relative_to(original).as_posix())
    eda = tmp_path / 'eda'; inspect_sources({'zip': str(zipped)}, eda)
    plan_path = eda / 'plan.json'; plan = json.loads(plan_path.read_text())
    plan.update(reviewed=True, split_reviewed=True)
    plan_path.write_text(json.dumps(plan))
    prepare_dataset(plan_path, tmp_path / 'prepared')
    assert verify_prepared(tmp_path / 'prepared/data.yaml')['images'] == 3
    assert list(zipped.iterdir()) == [zipped / 'sample.zip']
    plan = reviewed_plan(tmp_path / 'second')
    (tmp_path / 'second/raw/data.yaml').write_text('names: [W.227]')
    with pytest.raises(ValueError, match='Unmapped'):
        prepare_dataset(plan, tmp_path / 'new')


def test_evaluation_requires_matching_taxonomy_and_records_test_metrics(tmp_path):
    plan = reviewed_plan(tmp_path)
    data = tmp_path / 'prepared'; prepare_dataset(plan, data)
    model = tmp_path / 'best.pt'; model.write_bytes(b'fixture')
    calls = []

    class FakeYOLO:
        task = 'detect'
        names = {0: 'P.102'}

        def __init__(self, *_args, **_kwargs):
            pass

        def val(self, **kwargs):
            calls.append(kwargs)
            return type('Metrics', (), {'results_dict': {'metrics/mAP50(B)': .5}})()

    run_model('evaluate', data / 'data.yaml', str(model), tmp_path / 'evaluation', yolo_factory=FakeYOLO)
    report = json.loads((tmp_path / 'evaluation/pipeline_report.json').read_text())
    assert calls[0]['split'] == 'test' and report['test_evaluated'] is True
    assert report['metrics']['metrics/mAP50(B)'] == .5
    FakeYOLO.names = {0: 'wrong'}
    with pytest.raises(ValueError, match='taxonomy'):
        run_model('evaluate', data / 'data.yaml', str(model), tmp_path / 'wrong', yolo_factory=FakeYOLO)


def test_training_uses_safe_windows_settings_and_does_not_evaluate_test(tmp_path):
    plan = reviewed_plan(tmp_path)
    data = tmp_path / 'prepared'; prepare_dataset(plan, data)
    calls = []

    class FakeYOLO:
        def __init__(self, model, task):
            calls.append(('load', model, task))

        def train(self, **kwargs):
            calls.append(('train', kwargs))
            weights = Path(kwargs['project']) / kwargs['name'] / 'weights'
            weights.mkdir(parents=True); (weights / 'best.pt').write_bytes(b'fixture')
            self.trainer = type('Trainer', (), {'best': weights / 'best.pt'})()

        def val(self, **kwargs):
            raise AssertionError('Do not evaluate held-out test while choosing training settings')

    with pytest.raises(ValueError, match='download'):
        run_model('train', data / 'data.yaml', 'yolo11s.pt', tmp_path / 'no-download', yolo_factory=FakeYOLO)
    run_model('train', data / 'data.yaml', 'yolo11s.pt', tmp_path / 'run',
              allow_download=True, epochs=1, yolo_factory=FakeYOLO)
    settings = calls[-1][1]
    assert settings['workers'] == 0 and settings['batch'] == 2
    assert settings['fliplr'] == 0 and settings['flipud'] == 0
    assert settings['amp'] is False and settings['cache'] is False
    report = json.loads((tmp_path / 'run/pipeline_report.json').read_text())
    assert report['names'] == ['P.102'] and report['test_evaluated'] is False
