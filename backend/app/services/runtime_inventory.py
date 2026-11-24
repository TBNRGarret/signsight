"""Read-only inventory. Candidates are for manual review, never automatic deletion."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3

from fastapi import HTTPException

from backend.app.services.image_store import ImageStore


def inventory_runtime(engine, storage_root, *, older_than_days=30, verify_images=False, now=None):
    if type(older_than_days) is not int or not 1 <= older_than_days <= 3650:
        raise ValueError('Inventory age must be 1..3650 days')
    if engine.dialect.name != 'sqlite' or not engine.url.database or engine.url.database == ':memory:':
        raise ValueError('Inventory requires an existing file-based SQLite database')
    database = Path(engine.url.database).resolve()
    if not database.is_file(): raise ValueError('Runtime database does not exist')
    now = now or datetime.now(timezone.utc)
    cutoff = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    cutoff -= timedelta(days=older_than_days)
    store = ImageStore(storage_root)
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        violations = [dict(table=r[0], rowid=r[1], parent=r[2], constraint=r[3])
                      for r in db.execute('PRAGMA foreign_key_check')]
        images = [dict(r) for r in db.execute(
            'SELECT id, storage_key, sha256, size_bytes, created_at FROM uploaded_images ORDER BY id')]
        protected = {r[0] for r in db.execute('''SELECT DISTINCT r.image_id FROM inference_runs r
            JOIN image_detections d ON d.run_id=r.id JOIN observations o ON o.detection_id=d.id
            UNION SELECT image_id FROM sign_reports''')}
        evidence = list(db.execute('SELECT image_url, image_hash FROM evidence'))
        hashes = {r[1] for r in evidence if r[1]}
        urls = {r[0] for r in evidence}
        runs = dict(db.execute('SELECT image_id, count(*) FROM inference_runs GROUP BY image_id'))
    candidates, missing, invalid, registered = [], [], [], set()
    for image in images:
        key, identity = image['storage_key'], image['id']
        registered.add(key)
        linked = identity in protected or image['sha256'] in hashes or f'/api/v1/images/{identity}/content' in urls
        if linked: protected.add(identity)
        created = datetime.fromisoformat(image['created_at'])
        created = created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created.astimezone(timezone.utc)
        if not linked and created < cutoff:
            candidates.append(dict(id=identity, storage_key=key, size_bytes=image['size_bytes'],
                                   created_at=image['created_at'], inference_runs=runs.get(identity,0)))
        try:
            path = store.path(key)
            if not path.is_file(): missing.append(identity)
            elif verify_images:
                with path.open('rb') as stream: actual = hashlib.file_digest(stream,'sha256').hexdigest()
                if path.stat().st_size != image['size_bytes'] or actual != image['sha256']:
                    invalid.append(identity)
        except (HTTPException, OSError):
            invalid.append(identity)
    untracked = []
    if store.root.is_dir():
        for path in sorted(store.root.iterdir()):
            if path.name in registered: continue
            if path.is_symlink() or not path.is_file():
                untracked.append(dict(name=path.name, kind='symlink_or_directory', old_enough=False))
                continue
            info = path.stat()
            untracked.append(dict(name=path.name,kind='file',size_bytes=info.st_size,
                                  old_enough=datetime.fromtimestamp(info.st_mtime,timezone.utc)<cutoff))
    return dict(read_only=True, older_than_days=older_than_days, hashes_verified=verify_images,
                database=dict(integrity=integrity, foreign_key_violations=violations),
                registered_images=len(images), registered_bytes=sum(r['size_bytes'] for r in images),
                protected_images=sum(r['id'] in protected for r in images),
                unused_upload_candidates=candidates, missing_images=missing,invalid_images=invalid,
                untracked_files=untracked,
                policy='No files or rows deleted. Candidates may still belong to local drafts or write receipts; '
                       'back up and inspect manually. Online inventory is not a deletion authorization.')
