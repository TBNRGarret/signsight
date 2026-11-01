import ast
import io
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from scripts.dataset_eda import DatasetReader, audit_dataset
from scripts.drive_eda_source import resolve_archive


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




