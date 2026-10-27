import json
import sqlite3
import zipfile
from contextlib import closing
import pytest

from backend.app.services.runtime_backup import create_runtime_backup, restore_runtime_backup
from test_reports_policy import user_and_image


def test_backup_restores_database_and_verified_images_without_overwriting_live_data(client, application, tmp_path):
    _, _, image = user_and_image(client)
    with application.state.session_factory() as db:
        engine = db.get_bind()
    archive = tmp_path / 'snapshot.zip'
    create_runtime_backup(engine, application.state.settings.storage_root, archive)
    target = tmp_path / 'recovery'
    restore_runtime_backup(archive, target)
    with closing(sqlite3.connect(target / 'signsight.db')) as restored:
        row = restored.execute('select storage_key, sha256 from uploaded_images').fetchone()
        assert restored.execute('select count(*) from users').fetchone()[0] == 1
        assert restored.execute('select count(*) from auth_sessions where revoked_at is null').fetchone()[0] == 0
    import hashlib
    assert hashlib.sha256((target / 'images' / row[0]).read_bytes()).hexdigest() == image['sha256'] == row[1]
    with pytest.raises(FileExistsError):
        restore_runtime_backup(archive, target)
    with pytest.raises(FileExistsError):
        create_runtime_backup(engine, application.state.settings.storage_root, archive)


def test_missing_image_aborts_without_publishing_a_partial_backup(client, application, tmp_path):
    user_and_image(client)
    for path in application.state.settings.storage_root.glob('*.jpg'):
        path.unlink()
    with application.state.session_factory() as db:
        engine = db.get_bind()
    archive = tmp_path / 'incomplete.zip'
    with pytest.raises(ValueError, match='image'):
        create_runtime_backup(engine, application.state.settings.storage_root, archive)
    assert not archive.exists()


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'images/../../outside', 'images\\..\\outside'])
def test_restore_rejects_unsafe_members_before_creating_target(tmp_path, name):
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(name, b'bad')
        output.writestr('manifest.json', json.dumps({'version': 1, 'files': {}}))
    with pytest.raises(ValueError):
        restore_runtime_backup(archive, tmp_path / 'target')
    assert not (tmp_path / 'target').exists()
