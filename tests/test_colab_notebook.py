import ast
import json
from pathlib import Path
import zipfile

import pytest
import yaml
from test_detection_pipeline import sources

ROOT = Path(__file__).resolve().parents[1]


def test_yolo_notebook_is_self_contained_and_has_training_evaluation_download():
    notebook = json.loads((ROOT/'notebooks/SignSight_YOLO_Colab.ipynb').read_text(encoding='utf-8'))
    assert notebook['nbformat'] == 4
    code = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code')
    ast.parse(code)
    for required in ('ultralytics','train_detection','prepare_detection_data','validate_dataset','files.download','detection_report.json','yolo11n.pt'):
        assert required in code
    assert notebook['metadata']['accelerator'] == 'GPU'
    assert all(not cell.get('outputs') for cell in notebook['cells'])
    assert 'ai_engine/catalog.py' in code


def test_yolo_notebook_uses_kaggle_source_and_preserves_embedded_splits():
    from scripts.generate_yolo_notebook import build_notebook
    notebook=build_notebook()
    code='\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code')
    ast.parse(code)
    for required in ('kagglehub.dataset_download','KAGGLEHUB_CACHE','/kaggle/input','prepare_cached_dataset',
                     'restore_splits','SPLIT_PAYLOAD','SPLIT_CHECKSUMS','USE_DRIVE','PERSISTENT_CACHE'):
        assert required in code
    assert "DATASET_ZIP = Path('/content/signsight_yolo_dataset.zip')" not in code


def test_notebook_embedded_splits_match_repository_exactly(tmp_path):
    from ai_engine.notebook_data import restore_splits
    from scripts.generate_yolo_notebook import build_notebook
    notebook = build_notebook()
    packaged = json.loads((ROOT/'notebooks/SignSight_YOLO_Colab.ipynb').read_text(encoding='utf-8'))
    assert packaged == notebook
    setup = next(''.join(cell['source']) for cell in notebook['cells']
                 if cell['cell_type']=='code' and 'SPLIT_PAYLOAD =' in ''.join(cell['source']))
    assignments = {node.targets[0].id: ast.literal_eval(node.value)
                   for node in ast.parse(setup).body if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id in ('SPLIT_PAYLOAD','SPLIT_CHECKSUMS')}
    restored = restore_splits(assignments['SPLIT_PAYLOAD'], assignments['SPLIT_CHECKSUMS'], tmp_path)
    for path in restored.iterdir():
        assert path.read_bytes() == (ROOT/'data/processed'/path.name).read_bytes()


def test_notebook_cached_dataset_cell_runs_without_download_and_uses_absolute_runtime_yaml(sources, tmp_path, capsys):
    import ai_engine.notebook_data as module
    from scripts.generate_yolo_notebook import build_notebook
    archive, csv_root, _ = sources
    work = tmp_path/'work'; work.mkdir()
    portable, _ = module.prepare_cached_dataset(archive, csv_root, work/'.cache/yolo', source_id='test/v1')
    notebook = build_notebook()
    code = next(''.join(cell['source']) for cell in notebook['cells']
                if cell['cell_type']=='code' and "CACHE_ROOT = WORK" in ''.join(cell['source']))
    context = {name:getattr(module,name) for name in ('DatasetCacheMiss','prepare_cached_dataset','resolve_archive')}
    context.update(WORK=work, CSV_ROOT=csv_root, SOURCE_ID='test/v1', PERSISTENT_CACHE=None, json=json)
    capsys.readouterr()
    exec(code, context)
    output = capsys.readouterr().out
    assert len(output.splitlines()) <= 6
    assert all(f'{split}: 10 images / 10 boxes' in output for split in ('train', 'val', 'test'))
    assert context['DATASET_REPORT']['sha256'] not in output
    assert json.loads((work/'dataset_report.json').read_text()) == context['DATASET_REPORT']
    assert context['DATASET_ROOT'] == portable.parent
    assert yaml.safe_load(context['DATA'].read_text())['path'] == str(portable.parent.resolve())
    assert yaml.safe_load(portable.read_text())['path'] == '.'


def test_packaged_dataset_has_portable_yaml_and_cannot_overwrite(sources, tmp_path):
    from ai_engine.prepare_detection_data import build_dataset
    from scripts.package_yolo_dataset import package_dataset
    archive,csv_root,output = sources
    build_dataset(archive,csv_root,output)
    target = tmp_path/'dataset.zip'
    package_dataset(output,target)
    with zipfile.ZipFile(target) as bundle:
        config = yaml.safe_load(bundle.read('data.yaml'))
        assert config['path'] == '.' and config['test'] == 'images/test'
        assert 'manifest.json' in bundle.namelist()
        assert len([name for name in bundle.namelist() if name.startswith('labels/')]) == 30
    with pytest.raises(FileExistsError):
        package_dataset(output,target)
