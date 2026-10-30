"""Synthetic downloads only: never access personal Drive files or credentials."""
import hashlib
import io
from pathlib import Path
import zipfile

import pytest

from scripts.colab_downloads import download_drive_zip


FILE_ID = 'fixture_supsign_file_12345'
URL = f'https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing'


def archive_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('data.yaml', 'names: [No_entry]\n')
    return stream.getvalue()


def test_downloads_shared_zip_without_account_cookies_and_reuses_it(tmp_path):
    calls = []
    def download(**options):
        calls.append(options)
        Path(options['output']).write_bytes(archive_bytes())
        return options['output']
    target = tmp_path/'source.zip'
    assert download_drive_zip(URL, target, downloader=download) == target
    assert download_drive_zip(FILE_ID, target, downloader=download) == target
    assert len(calls) == 1
    assert calls[0]['resume'] is True and calls[0]['use_cookies'] is False
    assert calls[0]['id'] == FILE_ID


def test_retry_keeps_partial_download_but_never_publishes_it(tmp_path):
    attempts = []
    def download(**options):
        partial = Path(options['output']+'.part.tmp')
        attempts.append(options)
        if len(attempts) == 1:
            partial.write_bytes(b'incomplete')
            raise OSError('connection interrupted')
        assert partial.read_bytes() == b'incomplete'
        Path(options['output']).write_bytes(archive_bytes())
        return options['output']
    target = tmp_path/'source.zip'
    with pytest.raises(RuntimeError, match='Drive'):
        download_drive_zip(URL, target, downloader=download)
    assert not target.exists()
    download_drive_zip(URL, target, downloader=download)
    assert zipfile.is_zipfile(target)


@pytest.mark.parametrize('content', [b'<html>Permission denied</html>', b''])
def test_non_zip_response_never_reaches_preparation(tmp_path, content):
    def download(**options):
        Path(options['output']).write_bytes(content)
        return options['output']
    target = tmp_path/'source.zip'
    with pytest.raises(ValueError, match='ZIP'):
        download_drive_zip(URL, target, downloader=download)
    assert not target.exists()


def test_checksum_rejects_wrong_cache_and_can_adopt_matching_existing_zip(tmp_path):
    content = archive_bytes()
    def download(**options):
        Path(options['output']).write_bytes(content)
        return options['output']
    target = tmp_path/'source.zip'
    with pytest.raises(ValueError, match='SHA-256'):
        download_drive_zip(URL, target, expected_sha256='0'*64, downloader=download)
    assert not target.exists()
    other = tmp_path/'existing.zip'; other.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    assert download_drive_zip(URL, other, expected_sha256=checksum, downloader=download) == other


def test_changing_source_or_unknown_existing_file_never_overwrites_it(tmp_path):
    target = tmp_path/'source.zip'
    target.write_bytes(archive_bytes())
    original = target.read_bytes()
    with pytest.raises(FileExistsError): download_drive_zip(URL, target)
    checksum = hashlib.sha256(original).hexdigest()
    download_drive_zip(URL, target, expected_sha256=checksum)
    with pytest.raises(FileExistsError): download_drive_zip('different_fixture_file_12345', target)
    assert target.read_bytes() == original


@pytest.mark.parametrize('source', ['', 'YOUR_DRIVE_FILE_ID', 'https://example.com/file.zip',
                                  'https://drive.google.com/drive/folders/fixture12345678'])
def test_invalid_or_folder_source_is_rejected_before_network(tmp_path, source):
    with pytest.raises(ValueError, match='Drive'):
        download_drive_zip(source, tmp_path/'source.zip')
