import io
from PIL import Image
from test_accounts import register, login, headers, manager
from test_images_observations import owner, upload, picture, detect, submit


def test_thumbnail_is_bounded_jpeg_and_does_not_change_the_original(client):
    auth=owner(client)
    image=upload(client,auth,picture((960,720)))
    response=client.get(f"/api/v1/images/{image['id']}/thumbnail",headers=auth)
    assert response.status_code==200
    assert response.headers["content-type"]=="image/jpeg"
    assert response.headers["cache-control"]=="no-store"
    with Image.open(io.BytesIO(response.content)) as thumb:
        assert thumb.size==(320,240)
        assert not thumb.getexif()
    original=client.get(f"/api/v1/images/{image['id']}/content",headers=auth)
    with Image.open(io.BytesIO(original.content)) as source:
        assert source.size==(960,720)


def test_unsubmitted_thumbnail_is_private_and_requires_login(client):
    auth=owner(client)
    image=upload(client,auth)
    client.cookies.clear()
    assert client.get(f"/api/v1/images/{image['id']}/thumbnail").status_code==401
    register(client,"outsider")
    outsider=headers(login(client,"outsider")["access_token"])
    assert client.get(f"/api/v1/images/{image['id']}/thumbnail",headers=outsider).status_code==404


def test_accepted_evidence_thumbnail_follows_existing_image_access_rules(client,application):
    auth=owner(client)
    image=upload(client,auth)
    rows=submit(client,auth,image,detect(client,application,auth,image)).json()
    reviewer=headers(manager(client,application)["access_token"])
    response=client.post(f"/api/v1/manager/observations/{rows[0]['id']}/review",headers=reviewer,json={"action":"accept"})
    assert response.status_code==200
    register(client,"reader")
    reader=headers(login(client,"reader")["access_token"])
    assert client.get(f"/api/v1/images/{image['id']}/thumbnail",headers=reader).status_code==200
