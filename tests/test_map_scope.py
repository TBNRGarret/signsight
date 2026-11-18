import pytest

from test_accounts import register, login, headers
from test_navigation_map import add_sign


@pytest.fixture
def auth(client):
    register(client)
    return headers(login(client)['access_token'])


def test_map_radius_filters_before_count_and_pagination(client, application, auth):
    near = [add_sign(application, lat=10.78+i*.0001) for i in range(3)]
    add_sign(application, lat=10.8)
    # Inside the coarse square, outside the actual 300m circle.
    add_sign(application, lat=10.7825, lon=106.7025)
    add_sign(application, status='removed')
    params = dict(latitude=10.78, longitude=106.7, radius_meters=300, limit=1)
    response = client.get('/api/v1/map/signs', params=params, headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['total'] == 3
    all_ids = {body['items'][0]['id']}
    for offset in (1, 2):
        page = client.get('/api/v1/map/signs', params={**params, 'offset':offset}, headers=auth).json()
        assert page['total'] == 3
        all_ids.add(page['items'][0]['id'])
    assert all_ids == set(near)


def test_map_radius_combines_with_existing_class_status_and_viewport(client, application, auth):
    wanted = add_sign(application)
    add_sign(application, class_id=9)
    add_sign(application, status='removed')
    add_sign(application, lat=10.8)
    response = client.get('/api/v1/map/signs', headers=auth, params=dict(
        latitude=10.78, longitude=106.7, radius_meters=300, class_id=0, status='active',
        min_lat=10.77, max_lat=10.79, min_lon=106.69, max_lon=106.71))
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['id'] == wanted


@pytest.mark.parametrize('query', [
    'latitude=10.78', 'longitude=106.7', 'radius_meters=300',
    'latitude=10.78&longitude=106.7',
    'latitude=nan&longitude=106.7&radius_meters=300',
    'latitude=10.78&longitude=106.7&radius_meters=0',
    'latitude=10.78&longitude=106.7&radius_meters=1001',
])
def test_map_rejects_incomplete_or_invalid_radius_scope(client, auth, query):
    assert client.get('/api/v1/map/signs?'+query, headers=auth).status_code == 422


def test_map_radius_handles_longitude_wrap(client, application, auth):
    wanted = add_sign(application, lat=0, lon=-179.999)
    add_sign(application, lat=0, lon=-179.9)
    response = client.get('/api/v1/map/signs', headers=auth, params=dict(
        latitude=0, longitude=179.999, radius_meters=300))
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['id'] == wanted
