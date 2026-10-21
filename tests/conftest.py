import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.settings import Settings
from backend.app.db.database import make_engine
from backend.app.main import create_app


@pytest.fixture
def application(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    app = create_app(engine, Settings(storage_root=tmp_path / "uploads"))
    yield app
    engine.dispose()


@pytest.fixture
def client(application):
    with TestClient(application) as test_client:
        yield test_client
