import ast
import io
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from scripts.dataset_eda import DatasetReader, audit_dataset
from scripts.drive_eda_source import resolve_archive
from scripts.generate_drive_eda_notebook import build_notebook


def make_zip(path):
    image = io.BytesIO(); Image.new('RGB', (48, 32), 'red').save(image, format='PNG')
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('data.yaml', 'names: [P.102]\n')
        archive.writestr('images/train/a.png', image.getvalue())
        archive.writestr('labels/train/a.txt', '0 .5 .5 .25 .25\n')


def test_reader_accepts_one_zip_without_scanning_drive_parent_or_extracting(tmp_path):
    source = tmp_path / 'archive.zip'; make_zip(source)
    Image.new('RGB', (10, 10)).save(tmp_path / 'private-unrelated.png')
    with DatasetReader(source) as reader:
        report = audit_dataset(reader, 'drive', hash_limit=None, verify_decode=True)
        assert len(reader.zips) == 1
        assert not any('private-unrelated' in name for name in reader.entries)
    assert report['summary']['images_total'] == 1 and report['summary']['valid_boxes'] == 1
    assert report['boxes'][0]['class_name'] == 'P.102'
    assert not (tmp_path / 'images').exists()


def test_download_publishes_valid_zip_and_reuses_cached_file(tmp_path):
    fixture = tmp_path / 'fixture.zip'; make_zip(fixture)
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        Path(kwargs['output']).write_bytes(fixture.read_bytes())
        return kwargs['output']

    source = resolve_archive('public-id', tmp_path / 'cache', download=download)
    assert source.is_file() and zipfile.is_zipfile(source)
    assert calls[0]['id'] == 'public-id' and calls[0]['resume'] is True
    assert calls[0]['use_cookies'] is False
    assert resolve_archive('public-id', tmp_path / 'cache', download=download) == source
    assert len(calls) == 1


def test_download_rejects_html_without_publishing_a_fake_zip(tmp_path):
    def blocked(**kwargs):
        Path(kwargs['output']).write_text('<html>permission denied</html>')
        return kwargs['output']

    with pytest.raises(ValueError, match='ZIP'):
        resolve_archive('public-id', tmp_path / 'cache', download=blocked)
    assert not (tmp_path / 'cache/public-id/archive.zip').exists()
    assert not (tmp_path / 'cache/public-id/archive.zip.part').exists()
    assert len(list((tmp_path / 'cache/public-id').glob('archive.invalid-*.download'))) == 1


def test_local_mount_uses_original_file_without_download_or_copy(tmp_path):
    source = tmp_path / 'archive.zip'; make_zip(source)
    actual = resolve_archive('public-id', tmp_path / 'cache', local_archive=source,
                             download=lambda **kwargs: pytest.fail('must not download'))
    assert actual == source.resolve() and not (tmp_path / 'cache').exists()
    with pytest.raises(FileNotFoundError):
        resolve_archive('public-id', tmp_path / 'cache', local_archive=tmp_path / 'missing.zip')


@pytest.mark.parametrize('file_id', ['../escape', 'https://drive.google.com/file/d/id', '', 'id/other'])
def test_download_id_cannot_escape_cache_directory(tmp_path, file_id):
    with pytest.raises(ValueError, match='ID'):
        resolve_archive(file_id, tmp_path / 'cache', download=lambda **_: None)


def test_drive_notebook_is_standalone_generated_and_contains_the_supplied_file_id():
    notebook = build_notebook()
    target = Path(__file__).parents[1] / 'notebooks/SignSight_Drive_Dataset_EDA_Colab.ipynb'
    assert notebook == json.loads(target.read_text(encoding='utf-8'))
    code = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
    assert 'YOUR_DRIVE_FILE_ID' in code
    assert 'gdown' in code and 'kagglehub' not in code
    assert 'extractall' not in code and 'files.download' in code
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            ast.parse(''.join(cell['source']))
            assert cell['outputs'] == [] and cell['execution_count'] is None


@pytest.mark.parametrize('mode', ['download', 'drive'])
def test_drive_notebook_cells_execute_from_mock_download_to_report_zip(tmp_path, monkeypatch, mode):
    from datetime import datetime, timezone
    import importlib.metadata
    import shutil
    import sys
    import types
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    import pandas as pd
    from scripts.generate_drive_eda_notebook import FILE_ID

    source = tmp_path / 'input.zip'; make_zip(source)
    work = tmp_path / 'work'; work.mkdir()
    out = tmp_path / 'report'; out.mkdir()
    downloaded = []
    fake_gdown = types.ModuleType('gdown')

    def download(**kwargs):
        assert mode == 'download'
        assert kwargs['id'] == FILE_ID
        Path(kwargs['output']).write_bytes(source.read_bytes())
        return kwargs['output']

    fake_gdown.download = download
    google = types.ModuleType('google'); colab = types.ModuleType('google.colab')
    colab.files = types.SimpleNamespace(download=downloaded.append); google.colab = colab
    monkeypatch.setitem(sys.modules, 'gdown', fake_gdown)
    monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setitem(sys.modules, 'google.colab', colab)
    monkeypatch.setattr(importlib.metadata, 'version', lambda _: 'fixture-version')
    monkeypatch.setattr(plt, 'show', lambda: None)
    context = dict(Path=Path, WORK=work, CACHE=work / 'cache', OUT=out, FILE_ID=FILE_ID,
                   SOURCE_MODE=mode, DRIVE_ARCHIVE=str(source), PERSISTENT=None,
                   ACTIVE_DATASETS=['drive_dataset'], SOURCE_ERRORS=[], MAX_IMAGES=None,
                   HASH_LIMIT=None, VERIFY_DECODE=True, ANNOTATION_FORMAT='yolo', SEED=42, zipfile=zipfile,
                   json=json, importlib=__import__('importlib'), pd=pd, plt=plt, patches=patches,
                   Image=Image, display=lambda *_: None, tqdm=lambda values, **_: values,
                   datetime=datetime, timezone=timezone, shutil=shutil)
    cells = [''.join(cell['source']) for cell in build_notebook()['cells'] if cell['cell_type'] == 'code']
    try:
        for marker in ('EDA_SOURCE =', 'archive_path =', 'for old_reader', 'class_columns =', 'chosen =', 'def export_csv'):
            exec(next(cell for cell in cells if cell.startswith(marker)), context)
        summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        assert summary['source_file_id'] == (FILE_ID if mode == 'download' else None)
        assert summary['requested_drive_file_id'] == FILE_ID and summary['source_mode'] == mode
        assert summary['datasets']['drive_dataset']['images_scanned'] == 1
        assert summary['datasets']['drive_dataset']['valid_boxes'] == 1
        assert summary['datasets']['drive_dataset']['annotation_format'] == 'yolo'
        assert summary['versions']['gdown'] == 'fixture-version'
        assert (out / 'samples.png').stat().st_size > 1000
        assert (out / 'distributions.png').stat().st_size > 1000
        with zipfile.ZipFile(downloaded[0]) as report:
            assert {'summary.json', 'inventory.csv', 'class_counts.csv', 'boxes.csv', 'samples.png'} <= set(report.namelist())
            assert not any(name.endswith('.zip') for name in report.namelist())
    finally:
        for reader in context.get('READERS', {}).values():
            reader.close()
        plt.close('all')
