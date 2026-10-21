import httpx
import pytest
from fastapi import HTTPException

from backend.app.core.settings import Settings
from backend.app.services.routing_service import PhotonPlaceProvider, make_place_provider, PlaceProvider
from test_accounts import register, login, headers


def feature(osm_id, city='Thành phố Hồ Chí Minh', country='VN', **properties):
    return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [106.7, 10.78]},
            'properties': {'osm_type': 'W', 'osm_id': osm_id, 'name': 'Nguyễn Huệ',
                           'city': city, 'countrycode': country, 'country': 'Việt Nam', **properties}}


def provider(features, calls=None):
    def transport(request):
        if calls is not None:
            calls.append(request)
        return httpx.Response(200, json={'type': 'FeatureCollection', 'features': features})
    return PhotonPlaceProvider('https://photon.example', 'SignSight tests', transport=httpx.MockTransport(transport))


def test_photon_adapter_biases_hcm_sorts_before_limit_and_caches():
    calls = []
    candidates = [feature(i, city='Hà Nội') for i in range(1, 7)] + [feature(7), feature(8)]
    p = provider(candidates, calls)
    items = p.search('Nguyễn Huệ')
    assert [item['id'] for item in items] == ['photon:W:7', 'photon:W:8', 'photon:W:1', 'photon:W:2', 'photon:W:3']
    assert items[0]['latitude'] == 10.78 and items[0]['longitude'] == 106.7
    assert 'Thành phố Hồ Chí Minh' in items[0]['name']
    assert p.search('  NGUYỄN   HUỆ  ') == items and len(calls) == 1
    request = calls[0]
    assert request.url.path == '/api/'
    assert request.url.params['q'] == 'Nguyễn Huệ'
    assert float(request.url.params['lat']) == 10.7769 and float(request.url.params['lon']) == 106.7009
    assert request.url.params['limit'] == '20'
    assert 'bbox' not in request.url.params and 'countrycode' not in request.url.params


def test_photon_keeps_other_cities_and_never_promotes_business_name_as_a_city():
    outside = feature(1, city='Hà Nội', name='Ho Chi Minh Cafe')
    hcm = feature(2)
    abroad = feature(3, city='Ho Chi Minh City', country='US')
    assert [item['id'] for item in provider([outside, hcm, abroad]).search('địa điểm')] == [
        'photon:W:2', 'photon:W:1', 'photon:W:3']


def test_photon_address_can_use_house_number_and_street_without_poi_name():
    item = feature(1, name=None, housenumber='35', street='Bạch Đằng', district='Bình Thạnh')
    result = provider([item]).search('35 Bạch Đằng')[0]
    assert result['name'].startswith('35 Bạch Đằng, Bình Thạnh,')
    assert provider([]).search('không có địa điểm') == []


@pytest.mark.parametrize('change', [
    {'geometry': {'type': 'LineString', 'coordinates': [106.7, 10.78]}},
    {'geometry': {'type': 'Point', 'coordinates': [10.78, 106.7]}},
    {'geometry': {'type': 'Point', 'coordinates': [106.7, 10.78, 5]}},
    {'properties': {'name': 'No ID'}},
    {'properties': {'osm_type': 'W', 'osm_id': 1, 'name': {'bad': 'text'}}},
])
def test_invalid_photon_results_are_errors_and_not_cached(change):
    p = provider([{**feature(1), **change}])
    with pytest.raises(HTTPException) as error:
        p.search('địa điểm')
    assert error.value.status_code == 502 and not p.cache


def test_photon_provider_failure_is_not_an_empty_success_and_does_not_request_nominatim():
    calls = []
    def fail(request):
        calls.append(request)
        return httpx.Response(503)
    p = PhotonPlaceProvider('https://photon.example', 'SignSight tests', transport=httpx.MockTransport(fail))
    with pytest.raises(HTTPException) as error:
        p.search('Nguyễn Huệ')
    assert error.value.status_code == 502 and len(calls) == 1 and not p.cache


def test_photon_is_default_but_configured_legacy_nominatim_is_preserved(monkeypatch):
    monkeypatch.delenv('SIGNSIGHT_PLACES_PROVIDER', raising=False)
    monkeypatch.delenv('SIGNSIGHT_PLACES_BASE_URL', raising=False)
    settings = Settings.from_env()
    assert settings.places_provider == 'photon' and settings.places_base_url == 'https://photon.komoot.io'
    assert isinstance(make_place_provider(settings), PhotonPlaceProvider)
    monkeypatch.setenv('SIGNSIGHT_PLACES_BASE_URL', 'https://private-nominatim.example')
    legacy = Settings.from_env()
    assert legacy.places_provider == 'nominatim' and type(make_place_provider(legacy)) is PlaceProvider
    monkeypatch.setenv('SIGNSIGHT_PLACES_PROVIDER', 'photon')
    assert Settings.from_env().places_provider == 'photon'
    with pytest.raises(ValueError, match='places provider'):
        Settings(places_provider='unrecognized')


def test_places_api_normalizes_photon_for_existing_frontend(client, application):
    register(client)
    auth = headers(login(client)['access_token'])
    application.state.place_provider = provider([feature(1)])
    response = client.get('/api/v1/places/search', params={'q': 'Nguyễn Huệ'}, headers=auth)
    assert response.status_code == 200
    assert response.json()['provider'] == 'photon'
    assert response.json()['items'][0]['id'] == 'photon:W:1'
