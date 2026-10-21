"""Run versioned migrations using an existing engine (including isolated test DBs)."""

from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import uuid

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect


def migration_config():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    return config


def upgrade_database(engine):
    config = migration_config()
    sqlite_path = engine.url.database if engine.dialect.name == "sqlite" else None
    if sqlite_path and sqlite_path != ":memory:" and Path(sqlite_path).is_file():
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            has_data_schema = bool(inspect(connection).get_table_names())
        head = ScriptDirectory.from_config(config).get_current_head()
        if has_data_schema and current != head:
            backup_sqlite_database(engine)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def backup_sqlite_database(engine):
    database = engine.url.database
    if engine.dialect.name != "sqlite" or not database or database == ":memory:":
        raise ValueError("This backup command requires a file-based SQLite database")
    source = Path(database).resolve()
    if not source.is_file():
        raise ValueError("SQLite database does not exist yet")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = source.parent / "backups" / f"{source.stem}.{stamp}.{uuid.uuid4().hex[:8]}.sqlite3"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # SQLite's backup API also includes committed data in an active WAL file.
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(str(destination)) as backup:
            original.backup(backup)
    return destination


def require_current_database(engine):
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    head = ScriptDirectory.from_config(migration_config()).get_current_head()
    if current != head:
        raise RuntimeError("Database requires migration: run python -m backend.manage migrate")
