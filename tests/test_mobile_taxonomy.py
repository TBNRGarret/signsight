from ai_engine.config import TAXONOMY
from test_accounts import register, login, headers


def test_mobile_catalogue_requires_login_and_preserves_order_before_manual_others(client):
    assert client.get('/api/v1/taxonomy').status_code == 401
    register(client)
    auth = headers(login(client)['access_token'])
    response = client.get('/api/v1/taxonomy', headers=auth)
    assert response.status_code == 200
    items=response.json()['items']
    assert items[:-1] == [
        {key: item[key] for key in ('new_id', 'qcvn_code', 'name_vi')}
        for item in TAXONOMY
    ]
    assert items[-1] == {'new_id':1000000,'qcvn_code':'OTHER','name_vi':'Khác / Others'}
