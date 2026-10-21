import os
from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "backend", "signsight.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

def make_engine(url: str, **kwargs):
    db_engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        **kwargs,
    )
    if db_engine.dialect.name == "sqlite":
        @event.listens_for(db_engine, "connect")
        def configure_sqlite(connection, _):
            # Explicit BEGIN below makes DDL migrations transactional on Python 3.11.
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        @event.listens_for(db_engine, "begin")
        def begin_sqlite(connection):
            connection.exec_driver_sql("BEGIN")
    return db_engine


engine = make_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db(db_engine=None):
    from backend.app.db.migrations import upgrade_database
    upgrade_database(db_engine if db_engine is not None else engine)

def get_db(request: Request):
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()
