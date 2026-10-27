"""Disposable API for browser tests; never uses a local user's database/model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    import tempfile
    import uuid
    from datetime import datetime, timedelta
    from backend.app.db.models import SignRecord
    from ai_engine.config import CLASS_MAPPING
    import uvicorn
    from backend.app.core.settings import Settings
    from backend.app.db.database import make_engine, init_db
    from backend.app.main import create_app
    from backend.app.schemas.auth import UserRegister
    from backend.app.services.auth_service import create_user
    from ai_engine.detection import DetectionResult, Prediction

    class FixtureDetector:
        def status(self):
            return {"ready": True, "reason": None, "model_version": "browser-fixture",
                    "confidence_threshold": 0.65}

        def predict(self, image):
            return DetectionResult("browser-fixture", [
                Prediction(5, 0.99, (image.width*.2, image.height*.2, image.width*.8, image.height*.8)),
            ])

    with tempfile.TemporaryDirectory(prefix="signsight-browser-") as temporary:
        directory = Path(temporary)
        engine = make_engine("sqlite:///" + str(directory / "test.db"))
        init_db(engine)
        app = create_app(engine, Settings(storage_root=directory / "images"))
        app.state.detector = FixtureDetector()
        @app.get('/test-map.json')
        def test_map():
            return {'version': 8, 'sources': {},
                    'layers': [{'id': 'background', 'type': 'background',
                                'paint': {'background-color': '#e8eee6'}}]}
        with app.state.session_factory() as db:
            create_user(db, UserRegister(username="browser_manager", email="manager@example.com",
                                        password="Browser-test-password-123"), role="manager")
            create_user(db, UserRegister(username="browser_admin", email="admin@example.com",
                                        password="Browser-test-password-123"), role="admin")
            info = CLASS_MAPPING[0]
            for index in range(65):
                db.add(SignRecord(id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"browser-sign-{index}")),
                                  predicted_class=0, qcvn_code=info['qcvn_code'], name_vi=info['name_vi'],
                                  confidence=.95, latitude=21.03, longitude=105.8,
                                  status='removed' if index % 2 else 'active',
                                  verification_status='current', confirmation_days=30,
                                  expires_at=datetime.utcnow()+timedelta(days=30)))
            db.commit()

        try:
            uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
        finally:
            engine.dispose()
