import json
from zipfile import ZipFile

import pytest


def test_mtsd_inspection_uses_official_train_list_and_exact_speed_candidates(tmp_path):
    from training.data.mtsd import inspect_mtsd
    source = tmp_path / 'annotations.zip'
    with ZipFile(source, 'w') as archive:
        archive.writestr('splits/train.txt', 'a\nc\n')
        archive.writestr('splits/val.txt', 'b\n')
        for key, labels in {
            'a': ['regulatory--maximum-speed-limit-50--g1', 'regulatory--maximum-speed-limit-50--g2'],
            'b': ['regulatory--maximum-speed-limit-60--g1'],
            'c': ['regulatory--minimum-speed-limit-50--g1'],
        }.items():
            archive.writestr(f'annotations/{key}.json', json.dumps(dict(
                width=100, height=80, objects=[dict(label=label, bbox=dict(xmin=10, ymin=10, xmax=30, ymax=40)) for label in labels])))
    report = inspect_mtsd(source)
    assert report['summary']['annotation_images'] == 3
    assert [r['image_key'] for r in report['train_candidates']] == ['a']
    assert report['mapping_candidates'] == [dict(source_label='regulatory--maximum-speed-limit-50--g1', target='Speed_limit_50', reviewed='no'),
                                             dict(source_label='regulatory--maximum-speed-limit-60--g1', target='Speed_limit_60', reviewed='no')]
    assert report['summary']['automatic_training_ready'] is False


def test_mtsd_inspection_fails_when_train_membership_is_unknown_or_ambiguous(tmp_path):
    from training.data.mtsd import inspect_mtsd
    source = tmp_path / 'annotations.zip'
    with ZipFile(source, 'w') as archive:
        archive.writestr('annotations/a.json', json.dumps(dict(objects=[])))
    with pytest.raises(ValueError, match='train.txt'):
        inspect_mtsd(source)
    with ZipFile(source, 'a') as archive:
        archive.writestr('splits/train.txt', 'a\n')
        archive.writestr('splits/val.txt', 'a\n')
    with pytest.raises(ValueError, match='overlap'):
        inspect_mtsd(source)


def test_mtsd_inspection_reports_partial_annotation_and_does_not_read_images(tmp_path):
    from training.data.mtsd import inspect_mtsd
    source = tmp_path / 'annotations.zip'
    with ZipFile(source, 'w') as archive:
        archive.writestr('splits/train.txt', 'a\n')
        archive.writestr('annotations/a.json', json.dumps(dict(objects=[], is_fully_annotated=False)))
        archive.writestr('images/a.jpg', 'not an image')
    report = inspect_mtsd(source)
    assert report['summary']['explicitly_partial_images'] == 1
    assert report['train_candidates'] == []


def test_mtsd_notebook_embeds_current_helpers_and_runs_without_repository(tmp_path):
    import ast
    from training.notebooks.mtsd import build_mtsd_notebook, TARGET
    notebook = build_mtsd_notebook()
    assert json.loads(TARGET.read_text(encoding='utf-8')) == notebook
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            ast.parse(''.join(cell['source']))
            assert cell['outputs'] == [] and cell['execution_count'] is None
    source = next(''.join(c['source']) for c in notebook['cells'] if c['id'] == 'pipeline')
    parsed = ast.parse(source)
    embedded = ast.literal_eval(next(n.value for n in parsed.body if isinstance(n, ast.Assign) and
                                   any(isinstance(t, ast.Name) and t.id == 'SOURCES' for t in n.targets)))
    for name, content in embedded.items():
        assert content == (TARGET.parents[1] / name).read_text(encoding='utf-8')
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    # A clean process prevents the working checkout from satisfying imports.
    import subprocess, sys
    result = subprocess.run([sys.executable, '-c', 'from training.data.mtsd import inspect_mtsd; print(callable(inspect_mtsd))'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True'
