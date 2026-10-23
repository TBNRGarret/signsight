from fastapi.testclient import TestClient
from backend.app.core.settings import Settings
from backend.app.main import create_app


def test_user_preview_is_optional_and_only_serves_built_public_assets(tmp_path, application):
    build = tmp_path / 'flutter_build'
    build.mkdir()
    (build / 'index.html').write_text('<html><title>SignSight user</title></html>')
    (build / 'main.dart.js').write_text('console.log("fixture");')
    app = create_app(application.state.session_factory.kw['bind'], Settings(storage_root=tmp_path/'images'), user_app_directory=build)
    with TestClient(app) as client:
        assert client.get('/app/').status_code == 200
        assert 'SignSight user' in client.get('/app/').text
        assert client.get('/app/main.dart.js').status_code == 200
        assert client.get('/api/v1/me/observations').status_code == 401
        assert client.get('/app/../backend/signsight.db').status_code == 404


def test_missing_build_has_no_broken_static_mount(tmp_path, application):
    app = create_app(application.state.session_factory.kw['bind'], Settings(storage_root=tmp_path/'images'), user_app_directory=tmp_path/'not-built')
    with TestClient(app) as client:
        assert client.get('/app/').status_code == 404
        assert client.get('/web/index.html').status_code == 200
