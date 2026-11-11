"""Legacy reads must use the same session boundary as the current map API."""
from datetime import datetime, timedelta

import pytest

from backend.app.api.v1.endpoints import navigation, signs
from backend.app.db.models import AuthSession, User
from test_accounts import administrator, headers, login, manager, register
from test_navigation_map import add_sign

POINTS = [{'latitude': 10.779, 'longitude': 106.7}, {'latitude': 10.781, 'longitude': 106.7}]


def read(client, route, auth=None):
    if route == 'list':
        return client.get('/api/v1/signs', headers=auth or {})
    return client.post('/api/v1/navigation/route-signs', headers=auth or {},
                       json={'waypoints': POINTS, 'buffer_meters': 50})


@pytest.mark.parametrize('route', ['list', 'route'])
@pytest.mark.parametrize('credential', ['guest', 'invalid', 'expired', 'revoked', 'inactive'])
def test_legacy_reads_authenticate_before_route_work(client, application, monkeypatch, route, credential):
    auth = None
    if credential == 'invalid':
        auth = headers('invalid-token')
    elif credential != 'guest':
        account = register(client)
        session = login(client)
        auth = headers(session['access_token'])
        with application.state.session_factory() as db:
            if credential == 'inactive':
                db.get(User, account['id']).is_active = False
            else:
                saved = db.query(AuthSession).filter(AuthSession.user_id == account['id']).one()
                if credential == 'expired':
                    saved.expires_at = datetime.utcnow() - timedelta(minutes=1)
                else:
                    saved.revoked_at = datetime.utcnow()
            db.commit()
    work = []
    module = signs if route == 'list' else navigation
    monkeypatch.setattr(module, 'check_and_update_lifecycle_status', lambda db: work.append(True))
    response = read(client, route, auth)
    assert response.status_code == 401
    assert work == []


@pytest.mark.parametrize('role', ['user', 'manager', 'admin'])
def test_authenticated_legacy_reads_keep_shapes_filters_and_roles(client, application, role):
    if role == 'user':
        register(client)
        session = login(client)
    else:
        session = (manager if role == 'manager' else administrator)(client, application)
    auth = headers(session['access_token'])
    active = add_sign(application)
    removed = add_sign(application, status='removed')
    rows = read(client, 'list', auth)
    assert rows.status_code == 200
    assert isinstance(rows.json(), list)
    assert {row['id'] for row in rows.json()} == {active, removed}
    filtered = client.get('/api/v1/signs?status=removed', headers=auth)
    assert [row['id'] for row in filtered.json()] == [removed]
    route = read(client, 'route', auth)
    assert route.status_code == 200
    assert route.json()['route_points_count'] == 2
    assert [item['sign']['id'] for item in route.json()['signs']] == [active]
    if role == 'user':
        assert client.get('/api/v1/manager/summary', headers=auth).status_code == 403


def test_raw_route_reads_are_limited_before_geometry_work(client, application, monkeypatch):
    register(client)
    auth = headers(login(client)['access_token'])
    calls = []
    monkeypatch.setattr(navigation, 'route_signs', lambda *args: calls.append(True) or [])
    for _ in range(20):
        assert read(client, 'route', auth).status_code == 200
    response = read(client, 'route', auth)
    assert response.status_code == 429
    assert 'Retry-After' in response.headers
    assert len(calls) == 20
