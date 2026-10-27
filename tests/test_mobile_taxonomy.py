from ai_engine.config import TAXONOMY
from test_accounts import register, login, headers


def test_mobile_catalogue_requires_login_and_matches_runtime_class_order(client):
    assert client.get('/api/v1/taxonomy').status_code == 401
    register(client)
    auth = headers(login(client)['access_token'])
    response = client.get('/api/v1/taxonomy', headers=auth)
    assert response.status_code == 200
    assert response.json()['items'] == [
        {key: item[key] for key in ('new_id', 'qcvn_code', 'name_vi')}
        for item in TAXONOMY
    ]
