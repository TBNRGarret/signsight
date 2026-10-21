from datetime import datetime, timedelta

import pytest

from backend.app.core.security import hash_token
from backend.app.db.models import AuthSession, User
from test_accounts import PASSWORD, register

WEB = {'X-SignSight-Web': '1', 'Origin': 'http://testserver'}
COOKIE = 'signsight_session'


def web_login(client, **headers):
    return client.post('/api/v1/auth/login', headers={**WEB, **headers},
                       json={'username': 'alice', 'password': PASSWORD})


def test_browser_cookie_survives_page_navigation_and_logout_revokes_it(client):
    register(client)
    result = web_login(client)
    assert result.status_code == 200
    cookie = result.headers.get('set-cookie', '')
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    assert 'Path=/' in cookie and 'Max-Age=28800' in cookie
    token = result.json()['access_token']
    for page in ['index.html', 'observations.html', 'management.html']:
        assert client.get('/web/' + page).status_code == 200
        assert client.get('/api/v1/auth/me').json()['username'] == 'alice'
    assert client.post('/api/v1/auth/logout', headers=WEB).status_code == 204
    assert COOKIE not in client.cookies
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_remembered_browser_session_survives_8_hours_but_logout_still_revokes(client, application):
    register(client)
    result = client.post('/api/v1/auth/login', headers=WEB,
                         json={'username':'alice','password':PASSWORD,'remember_me':True})
    assert result.status_code == 200
    assert 'Max-Age=2592000' in result.headers['set-cookie']
    token = result.json()['access_token']
    with application.state.session_factory() as db:
        session = db.get(AuthSession, hash_token(token))
        assert timedelta(days=29) < session.expires_at - datetime.utcnow() <= timedelta(days=30)
    assert client.get('/api/v1/auth/me').status_code == 200
    assert client.post('/api/v1/auth/logout',headers=WEB).status_code == 204
    assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code == 401


@pytest.mark.parametrize('path',['/web/management.html','/web//management.html','/web/%6danagement.html'])
def test_guests_and_regular_users_cannot_open_management_page(client,path):
    guest=client.get(path,follow_redirects=False)
    assert guest.status_code == 303
    assert guest.headers['location'].startswith('/web/index.html?staff=')
    register(client);web_login(client)
    ordinary=client.get(path,follow_redirects=False)
    assert ordinary.status_code == 303
    assert ordinary.headers['location'].endswith('staff=forbidden')


@pytest.mark.parametrize('role',['manager','admin'])
def test_staff_page_checks_current_database_role_and_revocation(client,application,role):
    account=register(client)
    with application.state.session_factory() as db:
        db.get(User,account['id']).role=role;db.commit()
    web_login(client)
    allowed=client.get('/web/management.html',follow_redirects=False)
    assert allowed.status_code == 200
    assert allowed.headers['cache-control'] == 'no-store'
    with application.state.session_factory() as db:
        db.get(User,account['id']).role='user';db.commit()
    assert client.get('/web/management.html',follow_redirects=False).status_code == 303
    with application.state.session_factory() as db:
        db.get(User,account['id']).role=role;db.commit()
    assert client.post('/api/v1/auth/logout',headers=WEB).status_code == 204
    assert client.get('/web/management.html',follow_redirects=False).status_code == 303


def test_new_cookie_replaces_legacy_scoped_cookie_and_logout_clears_both(client):
    register(client)
    client.cookies.set(COOKIE,'old',domain='testserver.local',path='/api/v1')
    web_login(client)
    assert [cookie.path for cookie in client.cookies.jar if cookie.name == COOKIE] == ['/']
    assert client.post('/api/v1/auth/logout',headers=WEB).status_code == 204
    assert not [cookie for cookie in client.cookies.jar if cookie.name == COOKIE]


def test_remember_flag_does_not_extend_bearer_clients_or_trust_an_ip(client):
    register(client)
    response=client.post('/api/v1/auth/login',json={'username':'alice','password':PASSWORD,'remember_me':True})
    assert response.status_code == 200
    assert 'set-cookie' not in response.headers
    expires=datetime.fromisoformat(response.json()['expires_at'].replace('Z','+00:00')).replace(tzinfo=None)
    assert timedelta(hours=7) < expires-datetime.utcnow() <= timedelta(hours=8)
    assert client.get('/api/v1/auth/me').status_code == 401


@pytest.mark.parametrize('path',['/web/MANAGEMENT.HTML','/web/management.html.'])
def test_filesystem_aliases_never_expose_staff_html_to_guests(client,path):
    assert client.get(path,follow_redirects=False).status_code in (303,404)


@pytest.mark.parametrize('headers', [{}, {'Origin': 'http://evil.example', 'X-SignSight-Web': '1'},
                                   {'Origin': 'http://testserver'}])
def test_cookie_write_requires_same_origin_web_header(client, headers):
    register(client)
    web_login(client)
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 403
    assert client.get('/api/v1/auth/me').status_code == 200


def test_cross_origin_browser_login_is_rejected_before_creating_cookie(client):
    register(client)
    assert web_login(client, Origin='http://evil.example').status_code == 403
    assert COOKIE not in client.cookies


@pytest.mark.parametrize('authorization', ['Bearer wrong', 'Basic invalid'])
def test_invalid_explicit_bearer_does_not_fall_back_to_browser_cookie(client, authorization):
    register(client)
    web_login(client)
    assert client.get('/api/v1/auth/me', headers={'Authorization': authorization}).status_code == 401


def test_expired_browser_cookie_is_not_trusted(client, application):
    register(client)
    token = web_login(client).json()['access_token']
    with application.state.session_factory() as db:
        db.get(AuthSession, hash_token(token)).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get('/api/v1/auth/me').status_code == 401


def test_https_cookie_is_secure_and_bearer_login_keeps_existing_contract(client):
    register(client)
    ordinary = client.post('/api/v1/auth/login', json={'username': 'alice', 'password': PASSWORD})
    assert ordinary.status_code == 200 and 'set-cookie' not in ordinary.headers
    client.base_url = 'https://testserver'
    response = web_login(client, Origin='https://testserver')
    assert response.status_code == 200 and 'Secure' in response.headers['set-cookie']
    assert client.get('/api/v1/auth/me').status_code == 200
