from datetime import datetime, timedelta
from importlib import import_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.core.settings import Settings
from backend.app.db.database import make_engine
from backend.app.db.migrations import backup_sqlite_database, require_current_database, upgrade_database
from backend.app.db.models import SignRecord, User
from backend.app.main import create_app

legacy_metadata = import_module("backend.migrations.versions.0001_legacy_schema").legacy_metadata


def test_empty_database_and_repeat_migrations(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    try:
        upgrade_database(engine)
        upgrade_database(engine)
        assert not (tmp_path / "backups").exists()
        require_current_database(engine)
        assert {"users", "sign_records", "auth_sessions", "account_audit"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_catalog_provenance_upgrade_keeps_existing_inference_ids_and_labels(tmp_path):
    from alembic import command
    from backend.app.db.migrations import migration_config
    from sqlalchemy import MetaData, Table
    from backend.app.db.models import InferenceRun, ImageDetection
    engine=make_engine(f'sqlite:///{tmp_path / "previous.db"}')
    config=migration_config()
    with engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,'0005_duplicate_links')
    tables=MetaData()
    with engine.begin() as connection:
        users=Table('users',tables,autoload_with=connection)
        images=Table('uploaded_images',tables,autoload_with=connection)
        runs=Table('inference_runs',tables,autoload_with=connection)
        detections=Table('image_detections',tables,autoload_with=connection)
        connection.execute(users.insert(),dict(id='u',username='old',email='old@example.com',role='user',is_active=True,credential_version=0))
        connection.execute(images.insert(),dict(id='image',uploaded_by='u',storage_key='fixture.jpg',sha256='0'*64,
                                               size_bytes=1,width=32,height=32,created_at=datetime.utcnow()))
        connection.execute(runs.insert(),dict(id='run',image_id='image',engine='yolo',model_version='old-checkpoint',created_at=datetime.utcnow()))
        connection.execute(detections.insert(),dict(id='detection',run_id='run',ordinal=0,predicted_class=5,confidence=.9,
                                                    x1=1,y1=1,x2=20,y2=20))
    upgrade_database(engine)
    try:
        with sessionmaker(bind=engine)() as db:
            run=db.get(InferenceRun,'run');detection=db.get(ImageDetection,'detection')
            assert run.image_id=='image' and run.model_version=='old-checkpoint'
            assert run.mapping_sha256 is None and run.catalog_sha256 is None
            assert detection.predicted_class==5 and detection.model_class_id is None
        assert len(list((tmp_path/'backups').glob('*.sqlite3')))==1
    finally:
        engine.dispose()


def test_legacy_data_preserved_without_default_passwords(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    legacy_engine = create_engine(url)
    metadata = legacy_metadata()
    metadata.create_all(legacy_engine)
    with legacy_engine.begin() as connection:
        connection.execute(metadata.tables["users"].insert(), {
            "id": "old-user", "username": "legacy", "email": "legacy@example.com", "role": "contributor",
        })
        connection.execute(metadata.tables["sign_records"].insert(), {
            "id": "old-sign", "predicted_class": 0, "qcvn_code": "P.127 (50)", "name_vi": "Original sign",
            "confidence": .9, "latitude": 10.78, "longitude": 106.70, "created_by": "old-user",
            "expires_at": datetime.utcnow() + timedelta(days=30),
        })
    legacy_engine.dispose()
    engine = make_engine(url)
    try:
        upgrade_database(engine)
        upgrade_database(engine)
        backups = list((tmp_path / "backups").glob("*.sqlite3"))
        assert len(backups) == 1
        snapshot = create_engine(f"sqlite:///{backups[0]}")
        try:
            assert "password_hash" not in {column["name"] for column in inspect(snapshot).get_columns("users")}
            with snapshot.connect() as connection:
                assert len(connection.execute(select(metadata.tables["sign_records"])).all()) == 1
        finally:
            snapshot.dispose()
        with sessionmaker(bind=engine)() as db:
            user = db.get(User, "old-user")
            sign = db.get(SignRecord, "old-sign")
            assert user.role == "user" and user.is_active is False and user.password_hash is None
            assert sign.name_vi == "Original sign" and sign.created_by == "old-user"
            assert db.query(SignRecord).count() == 1
    finally:
        engine.dispose()


def test_ambiguous_legacy_identities_fail_without_partial_schema_changes(tmp_path):
    url = f"sqlite:///{tmp_path / 'ambiguous.db'}"
    legacy_engine = create_engine(url)
    metadata = legacy_metadata()
    metadata.create_all(legacy_engine)
    with legacy_engine.begin() as connection:
        connection.execute(metadata.tables["users"].insert(), [
            {"id": "first", "username": "Alice", "email": "first@example.com"},
            {"id": "second", "username": "alice", "email": "second@example.com"},
        ])
    legacy_engine.dispose()
    engine = make_engine(url)
    try:
        with pytest.raises(IntegrityError):
            upgrade_database(engine)
        assert "password_hash" not in {column["name"] for column in inspect(engine).get_columns("users")}
        assert "auth_sessions" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert len(connection.execute(select(metadata.tables["users"])).all()) == 2
    finally:
        engine.dispose()


def test_explicit_migration_required_when_auto_migrate_disabled(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'explicit.db'}")
    settings = Settings(auto_migrate=False)
    try:
        with pytest.raises(RuntimeError, match="requires migration"):
            with TestClient(create_app(engine, settings)):
                pass
        upgrade_database(engine)
        with TestClient(create_app(engine, settings)) as client:
            assert client.get("/").status_code == 200
    finally:
        engine.dispose()


def test_manual_sqlite_backup_keeps_existing_records(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'source.db'}")
    try:
        with pytest.raises(ValueError, match="does not exist"):
            backup_sqlite_database(engine)
        upgrade_database(engine)
        backup = backup_sqlite_database(engine)
        assert backup.is_file()
        copied = make_engine(f"sqlite:///{backup}")
        try:
            require_current_database(copied)
        finally:
            copied.dispose()
    finally:
        engine.dispose()
