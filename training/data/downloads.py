"""Download a shared Drive ZIP to local Colab storage, without account cookies."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse
import zipfile


def drive_file_id(source):
    source = str(source).strip()
    if not source or 'YOUR_' in source or 'PASTE_' in source:
        raise ValueError('Paste a shared Google Drive file URL or file ID')
    if '://' in source:
        parsed = urlparse(source)
        if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com' or parsed.username:
            raise ValueError('Use a Google Drive file link, not a folder or another website')
        match = re.fullmatch(r'/file/d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
        if match:
            source = match[1]
        elif parsed.path in ('/uc', '/open'):
            source = parse_qs(parsed.query).get('id', [''])[0]
        else:
            raise ValueError('Use a Google Drive file link, not a folder')
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,}', source):
        raise ValueError('Invalid Google Drive file ID')
    return source


def download_drive_zip(source, target, *, expected_sha256='', downloader=None):
    """Publish only a complete ZIP; source receipts prevent resuming another file.

    gdown owns its resumable temporary files. This helper keeps those on network
    failure and never overwrites a pre-existing target from an unknown source.
    An authoritative SHA-256 can adopt an already downloaded matching ZIP.
    """
    file_id = drive_file_id(source)
    checksum = str(expected_sha256).strip().lower()
    if checksum and not re.fullmatch('[a-f0-9]{64}', checksum):
        raise ValueError('Expected SHA-256 must have 64 hexadecimal characters')
    target = Path(target).resolve()
    receipt = target.with_name(target.name+'.source.json')
    staging = target.with_name(target.name+'.download')

    def validate(path):
        if not path.is_file() or not zipfile.is_zipfile(path):
            raise ValueError('Download is not a ZIP. Check Drive sharing, quota and the file link.')
        if checksum:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != checksum: raise ValueError('Downloaded ZIP SHA-256 mismatch')

    known = receipt.exists()
    if known:
        try:
            same_source = json.loads(receipt.read_text())['file_id'] == file_id
        except (ValueError, KeyError, TypeError):
            same_source = False
        if not same_source: raise FileExistsError('Local download belongs to another Drive file; choose a new path')
    elif target.exists():
        if not checksum: raise FileExistsError('Existing ZIP has no source receipt; supply its SHA-256 or choose a new path')
        validate(target)
    elif staging.exists() or any(target.parent.glob(staging.name+'*.tmp')):
        raise FileExistsError('Unknown partial download exists; choose a new local path')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not known:
        with receipt.open('x', encoding='utf-8') as stream:
            json.dump({'file_id': file_id}, stream)
    if target.exists():
        validate(target)
        return target
    if staging.exists():
        try:
            validate(staging)
        except ValueError:
            staging.unlink()  # Only the staging file identified by our matching receipt.
    if not staging.exists():
        if downloader is None:
            import gdown
            downloader = gdown.download
        try:
            result = downloader(id=file_id, output=str(staging), quiet=False,
                                resume=True, use_cookies=False)
        except Exception as error:
            raise RuntimeError('Drive download failed. Check public-link access/quota, then rerun this cell '
                               'to resume in the same runtime.') from error
        if result is None:
            raise RuntimeError('Drive returned no download. Check public-link access and download quota.')
    try:
        validate(staging)
    except ValueError:
        staging.unlink(missing_ok=True)
        raise
    if target.exists(): raise FileExistsError('Download target appeared; it was not overwritten')
    staging.rename(target)
    return target
