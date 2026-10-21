from datetime import datetime, timedelta

import httpx
import pytest

from backend.app.db.models import SignRecord
from test_accounts import register, login, headers


@pytest.fixture
def auth(client):
    register(client)
    return headers(login(client)['access_token'])


def add_sign(application,lat=10.78,lon=106.7,status='active',class_id=0,expired=False):
    from ai_engine.config import CLASS_MAPPING
    info=CLASS_MAPPING[class_id]
    with application.state.session_factory() as db:
        sign=SignRecord(predicted_class=class_id,qcvn_code=info['qcvn_code'],name_vi=info['name_vi'],confidence=.9,
                        latitude=lat,longitude=lon,status=status,confirmation_days=30,verification_status='current',
                        expires_at=datetime.utcnow()+timedelta(days=-1 if expired else 30))
        db.add(sign); db.commit(); return sign.id


def test_nearby_filters_distance_removed_and_paginates(client,application,auth):
    close=add_sign(application); farther=add_sign(application,lat=10.781)
    add_sign(application,lat=10.8); add_sign(application,status='removed')
    response=client.get('/api/v1/signs/nearby?latitude=10.78&longitude=106.7&radius_meters=300&limit=1',headers=auth)
    assert response.status_code==200,response.text
    body=response.json(); assert body['total']==2 and body['items'][0]['sign']['id']==close
    next_page=client.get('/api/v1/signs/nearby?latitude=10.78&longitude=106.7&radius_meters=300&limit=1&offset=1',headers=auth).json()
    assert next_page['items'][0]['sign']['id']==farther


def test_map_bounds_filters_detail_and_confirmation_requests(client,application,auth):
    stale=add_sign(application,expired=True); add_sign(application,lat=11); add_sign(application,class_id=9)
    response=client.get('/api/v1/map/signs?min_lat=10.7&max_lat=10.9&min_lon=106.6&max_lon=106.8&class_id=0',headers=auth)
    assert response.status_code==200,response.text
    assert response.json()['total']==1 and response.json()['items'][0]['id']==stale
    detail=client.get(f'/api/v1/signs/{stale}',headers=auth).json()
    assert detail['sign']['verification_status']=='needs_confirmation' and detail['evidence']==[]
    notices=client.get('/api/v1/me/confirmation-requests',headers=auth)
    assert notices.status_code==200 and notices.json()['total']==1


@pytest.mark.parametrize('query',['latitude=91&longitude=0','latitude=0&longitude=181','latitude=nan&longitude=0',
    'latitude=0&longitude=0&radius_meters=-1','latitude=0&longitude=0&radius_meters=100000'])
def test_nearby_rejects_invalid_coordinates_and_radius(client,auth,query):
    assert client.get('/api/v1/signs/nearby?'+query,headers=auth).status_code==422


def test_route_provider_uses_complete_geometry_and_signs_are_sorted_by_progress(client,application,auth):
    from backend.app.services.routing_service import RoutingProvider
    requested=[]
    def transport(request):
        requested.append(request)
        return httpx.Response(200,json={'code':'Ok','routes':[{'distance':2224,'duration':180,
                    'geometry':{'type':'LineString','coordinates':[[0,0],[.01,0],[.01,.01]]}}]})
    application.state.routing_provider=RoutingProvider('https://routing.example',transport=httpx.MockTransport(transport))
    later=add_sign(application,lat=.008,lon=.01)
    earlier=add_sign(application,lat=0,lon=.003)
    outside=add_sign(application,lat=.005,lon=.005)
    response=client.post('/api/v1/navigation/route',headers=auth,json={
        'origin':{'latitude':0,'longitude':0},'destination':{'latitude':.01,'longitude':.01},'buffer_meters':50})
    assert response.status_code==200,response.text
    body=response.json(); assert len(body['geometry'])==3 and body['provider']=='osrm'
    assert [row['sign']['id'] for row in body['signs']]==[earlier,later]
    assert body['signs'][0]['distance_along_route_meters'] < body['signs'][1]['distance_along_route_meters']
    assert requested[0].url.params['overview']=='full' and requested[0].url.params['geometries']=='geojson'


def test_route_provider_failure_is_an_error_not_a_straight_line(client,application,auth):
    from backend.app.services.routing_service import RoutingProvider
    application.state.routing_provider=RoutingProvider('https://routing.example',transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'code':'NoRoute'})))
    result=client.post('/api/v1/navigation/route',headers=auth,json={'origin':{'latitude':10,'longitude':106},'destination':{'latitude':11,'longitude':107}})
    assert result.status_code==502 and 'geometry' not in result.json()


def test_route_geometry_input_is_bounded_and_validated(client):
    for points in ([],[{'latitude':0,'longitude':0}],[{'latitude':99,'longitude':0},{'latitude':0,'longitude':0}]):
        assert client.post('/api/v1/navigation/route-signs',json={'waypoints':points,'buffer_meters':50}).status_code==422


def test_places_search_submits_explicit_query_and_caches_provider_results(client,application,auth):
    from backend.app.services.routing_service import PlaceProvider
    calls=[]
    def transport(request):
        calls.append(request)
        return httpx.Response(200,json=[{'place_id':1,'display_name':'Swinburne HCM','lat':'10.78','lon':'106.7'}])
    application.state.place_provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(transport))
    for _ in range(2):
        result=client.get('/api/v1/places/search?q=Swinburne',headers=auth)
        assert result.status_code==200,result.text
        assert result.json()['items'][0]['latitude']==10.78
    assert len(calls)==1
    assert client.get('/api/v1/places/search?q=x',headers=auth).status_code==422


def place_result(place_id,city,*,field='city',name=None,lat='10.78',lon='106.7'):
    return {'place_id':place_id,'display_name':name or f'Nguyễn Huệ, {city}, Việt Nam',
            'lat':lat,'lon':lon,'address':{field:city,'country_code':'vn'}}


def test_places_prioritizes_hcm_before_limiting_results_and_caches_ranked_page(client,application,auth):
    from backend.app.services.routing_service import PlaceProvider
    calls=[]
    candidates=[place_result(i,'Hà Nội',lat='21.03',lon='105.85') for i in range(1,7)]
    candidates += [place_result(7,'Thành phố Hồ Chí Minh',field='state'),
                   place_result(8,'Ho Chi Minh City')]
    def transport(request):
        calls.append(request)
        return httpx.Response(200,json=candidates)
    application.state.place_provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(transport))
    for query in ('Nguyễn Huệ','  NGUYỄN   HUỆ  '):
        response=client.get('/api/v1/places/search',params={'q':query},headers=auth)
        assert response.status_code==200,response.text
        assert [item['id'] for item in response.json()['items']]==['7','8','1','2','3']
    assert len(calls)==1
    params=calls[0].url.params
    assert params['q']=='Nguyễn Huệ'
    assert params['bounded']=='0' and 'countrycodes' not in params
    assert params['addressdetails']=='1' and params['accept-language']=='vi,en'
    assert int(params['limit'])>5
    west,north,east,south=map(float,params['viewbox'].split(','))
    assert west<106.7<east and south<10.78<north


@pytest.mark.parametrize(('field','city'),[
    ('city','Hồ Chí Minh'),('state','Thành phố Hồ Chí Minh'),
    ('municipality','Ho Chi Minh City'),('province','TP. Hồ Chí Minh'),
    ('state','Saigon'),
])
def test_places_recognizes_hcm_administrative_names(field,city):
    from backend.app.services.routing_service import PlaceProvider
    candidates=[place_result(1,'Hà Nội'),place_result(2,city,field=field)]
    provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=candidates)))
    assert [item['id'] for item in provider.search('Nguyễn Huệ')]==['2','1']


def test_places_preserves_destinations_outside_hcm_and_provider_relevance_order():
    from backend.app.services.routing_service import PlaceProvider
    candidates=[place_result(1,'Hà Nội',lat='21.03',lon='105.85'),
                {'place_id':2,'display_name':'Paris, France','lat':'48.86','lon':'2.35',
                 'address':{'city':'Paris','country_code':'fr'}}]
    provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=candidates)))
    assert [item['id'] for item in provider.search('Địa điểm')]==['1','2']


def test_places_uses_city_address_not_business_name_to_prioritize_hcm():
    from backend.app.services.routing_service import PlaceProvider
    candidates=[place_result(1,'Hà Nội',name='Ho Chi Minh Cafe, Hà Nội, Việt Nam'),
                place_result(2,'Hồ Chí Minh',name='Nguyễn Huệ, Việt Nam')]
    provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=candidates)))
    assert [item['id'] for item in provider.search('Nguyễn Huệ')]==['2','1']


def test_places_can_use_full_address_when_provider_omits_address_details():
    from backend.app.services.routing_service import PlaceProvider
    candidates=[{'place_id':1,'display_name':'Nguyễn Huệ, Hà Nội, Việt Nam','lat':'21.03','lon':'105.85'},
                {'place_id':2,'display_name':'Nguyễn Huệ, Thành phố Hồ Chí Minh, Việt Nam','lat':'10.78','lon':'106.7'}]
    provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=candidates)))
    assert [item['id'] for item in provider.search('Nguyễn Huệ')]==['2','1']


@pytest.mark.parametrize('payload',[
    {'error':'unavailable'},
    [place_result(i,'Hồ Chí Minh') for i in range(21)],
    [place_result(1,'Hồ Chí Minh',lat='nan')],
])
def test_places_still_rejects_invalid_provider_responses(payload):
    from backend.app.services.routing_service import PlaceProvider
    from fastapi import HTTPException
    provider=PlaceProvider('https://places.example','SignSight tests',transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))
    with pytest.raises(HTTPException) as error:
        provider.search('Nguyễn Huệ')
    assert error.value.status_code==502
