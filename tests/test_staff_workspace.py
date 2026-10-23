"""Staff catalogue is global, bounded and never exposed to ordinary users."""
import pytest
from backend.app.db.models import SignRecord
from test_accounts import register, login, headers, manager
from test_navigation_map import add_sign

@pytest.mark.parametrize('path',['/api/v1/manager/signs','/api/v1/manager/summary'])
def test_staff_catalogue_requires_staff(client,path):
    assert client.get(path).status_code == 401
    register(client)
    assert client.get(path,headers=headers(login(client)['access_token'])).status_code == 403

def test_staff_catalogue_covers_all_locations_and_statuses_with_stable_pagination(client,application):
    auth=headers(manager(client,application)['access_token'])
    ids={add_sign(application,lat=10+i,status='removed' if i==1 else 'active') for i in range(3)}
    pages=[client.get('/api/v1/manager/signs',params={'offset':i,'limit':1},headers=auth) for i in range(3)]
    assert all(p.status_code==200 for p in pages)
    assert all(p.json()['total']==3 and len(p.json()['items'])==1 for p in pages)
    assert {p.json()['items'][0]['id'] for p in pages}==ids
    assert pages[0].headers['cache-control']=='no-store'
    assert client.get('/api/v1/manager/signs?limit=101',headers=auth).status_code==422

def test_staff_catalogue_search_and_filters_apply_before_pagination(client,application):
    auth=headers(manager(client,application)['access_token'])
    wanted=add_sign(application,class_id=0,status='removed')
    add_sign(application,class_id=0);add_sign(application,class_id=5)
    response=client.get('/api/v1/manager/signs',params={'q':'P.127','status':'removed','limit':1},headers=auth)
    assert response.status_code==200,response.text
    assert response.json()['total']==1 and response.json()['items'][0]['id']==wanted
    for q in ['%','_']:
        assert client.get('/api/v1/manager/signs',params={'q':q},headers=auth).json()['total']==0
    assert client.get('/api/v1/manager/signs',params={'q':wanted},headers=auth).json()['total']==1
    assert client.get('/api/v1/manager/signs?status=unknown',headers=auth).status_code==422
    assert client.get('/api/v1/manager/signs?verification_status=unknown',headers=auth).status_code==422

def test_staff_summary_counts_work_without_returning_record_lists(client,application):
    auth=headers(manager(client,application)['access_token'])
    add_sign(application);add_sign(application,status='removed')
    response=client.get('/api/v1/manager/summary',headers=auth)
    assert response.status_code==200,response.text
    assert response.json()=={'contributions':0,'reports':0,'duplicates':0,'signs':2}
    assert response.headers['cache-control']=='no-store'
