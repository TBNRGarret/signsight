"""Portable, verified SQLite + managed image backups; restore only into a new root."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import zipfile

from backend.app.db.database import make_engine
from backend.app.db.migrations import require_current_database
from backend.app.services.image_store import ImageStore


def _hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _images(database):
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        if db.execute('pragma foreign_key_check').fetchone():
            raise ValueError('Database foreign-key check failed')
        return db.execute('select storage_key, sha256, size_bytes from uploaded_images').fetchall()


def create_runtime_backup(engine, storage_root, archive):
    """Snapshot committed WAL data, then copy the immutable images in that snapshot."""
    archive = Path(archive).resolve()
    if archive.exists():
        raise FileExistsError('Choose a new backup archive')
    database = engine.url.database
    if engine.dialect.name != 'sqlite' or not database or database == ':memory:':
        raise ValueError('Runtime backup requires a file-based SQLite database')
    source = Path(database).resolve()
    if not source.is_file():
        raise ValueError('Database does not exist')
    require_current_database(engine)
    archive.parent.mkdir(parents=True, exist_ok=True)
    store = ImageStore(storage_root)
    with tempfile.TemporaryDirectory(prefix='signsight-backup-', dir=archive.parent) as temporary:
        staging = Path(temporary).resolve()
        snapshot = staging / 'signsight.db'
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(snapshot)) as copied:
                original.backup(copied)
        images = _images(snapshot)
        files = {'signsight.db': {'sha256': _hash(snapshot), 'size': snapshot.stat().st_size}}
        # Validate everything before opening the final archive, then hash the actual bytes copied.
        (staging / 'images').mkdir()
        for key, expected, size in images:
            try:
                data = store.read(key, expected)
            except Exception as error:
                raise ValueError(f'Missing or invalid managed image: {key}') from error
            if len(data) != size:
                raise ValueError(f'Managed image size mismatch: {key}')
            relative = f'images/{key}'
            (staging / relative).write_bytes(data)
            files[relative] = {'sha256': expected, 'size': size}
        manifest = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                    'scope': 'database_and_managed_images', 'files': files}
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        # Exclusive create never overwrites an earlier backup; a failed write removes only our file.
        with archive.open('xb') as stream:
            try:
                with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as output:
                    for relative in ['manifest.json', *files]:
                        output.write(staging / relative, relative)
            except BaseException:
                stream.close()
                archive.unlink(missing_ok=True)
                raise
    return archive


def restore_runtime_backup(archive, target):
    """Verify before publishing. Never mutates the currently configured DB or images."""
    target = Path(target).resolve()
    if target.exists():
        raise FileExistsError('Restore requires a new directory; do not overwrite a running instance')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        names = [item.filename for item in members]
        if len(set(names)) != len(names) or 'manifest.json' not in names:
            raise ValueError('Invalid or duplicate backup members')
        allowed = re.compile(r'(manifest\.json|signsight\.db|images/[a-f0-9-]{36}\.jpg)')
        if any(not allowed.fullmatch(item.filename) or item.is_dir() or
               (item.external_attr >> 16) & 0o170000 == 0o120000 for item in members):
            raise ValueError('Unsafe backup member')
        if source.getinfo('manifest.json').file_size > 16 * 1024 * 1024:
            raise ValueError('Backup manifest too large')
        manifest = json.loads(source.read('manifest.json'))
        files = manifest.get('files')
        if manifest.get('version') != 1 or not isinstance(files, dict) or 'signsight.db' not in files:
            raise ValueError('Unsupported backup manifest')
        if set(names) != {'manifest.json', *files}:
            raise ValueError('Backup member inventory mismatch')
        for name, meta in files.items():
            limit = 4 * 1024**3 if name == 'signsight.db' else 50 * 1024**2
            if (not isinstance(meta, dict) or type(meta.get('size')) is not int or
                not 0 <= meta['size'] <= limit or source.getinfo(name).file_size != meta['size'] or
                not re.fullmatch('[a-f0-9]{64}', str(meta.get('sha256')))):
                raise ValueError('Invalid backup metadata')
        with tempfile.TemporaryDirectory(prefix='signsight-restore-', dir=target.parent) as temporary:
            staging = Path(temporary).resolve() / 'runtime'
            staging.mkdir()
            for name, meta in files.items():
                output = staging / name
                output.parent.mkdir(parents=True, exist_ok=True)
                with source.open(name) as incoming, output.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                if _hash(output) != meta['sha256']:
                    raise ValueError('Backup checksum mismatch')
            snapshot = staging / 'signsight.db'
            expected_images = {f'images/{key}': (checksum, size) for key, checksum, size in _images(snapshot)}
            if set(expected_images) != set(files) - {'signsight.db'} or any(
                (files[key]['sha256'], files[key]['size']) != value for key, value in expected_images.items()
            ):
                raise ValueError('Database/image inventory mismatch')
            copied = make_engine(f'sqlite:///{snapshot}')
            try:
                require_current_database(copied)
            finally:
                copied.dispose()
            # A restore must not resurrect sessions revoked since the snapshot.
            with closing(sqlite3.connect(snapshot)) as db:
                db.execute("update auth_sessions set revoked_at = coalesce(revoked_at, ?) ",
                           (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),))
                db.commit()
            (staging / 'images').mkdir(exist_ok=True)
            (staging / 'backup_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            if target.exists():
                raise FileExistsError('Restore target appeared during verification')
            staging.rename(target)
    return target
