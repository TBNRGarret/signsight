import io
from datetime import timedelta

from PIL import Image

from backend.app.db.models import SignRecord,Evidence,ConfirmationEvent
from test_accounts import register,login,headers,manager,administrator
from test_navigation_map import add_sign


def user_and_image(client):
    user=register(client); auth=headers(login(client)['access_token'])
    output=io.BytesIO(); Image.new('RGB',(64,64),'red').save(output,format='PNG')
    response=client.post('/api/v1/images',headers=auth,files={'file':('proof.png',output.getvalue(),'image/png')})
    assert response.status_code==201
    return user,auth,response.json()


def report(client,auth,image,record_id,action='confirm_existing',**kwargs):
    return client.post(f'/api/v1/signs/{record_id}/reports',headers=auth,json={'action':action,'image_id':image['id'],'comment':'Checked on road',**kwargs})


def test_user_report_cannot_change_a_sign_until_manager_accepts(client,application):
    record_id=add_sign(application,expired=True); user,auth,image=user_and_image(client)
    before=client.get(f'/api/v1/signs/{record_id}',headers=auth).json()['sign']
    created=report(client,auth,image,record_id)
    assert created.status_code==201,created.text
    report_id=created.json()['id']
    path=f'/api/v1/manager/reports/{report_id}/review'
    assert client.post(path,headers=auth,json={'action':'accept'}).status_code==403
    still=client.get(f'/api/v1/signs/{record_id}',headers=auth).json()['sign']
    assert still['expires_at']==before['expires_at'] and still['status']=='expired'
    reviewer=headers(manager(client,application)['access_token'])
    assert client.get(image['content_url'],headers=reviewer).status_code==200
    accepted=client.post(path,headers=reviewer,json={'action':'accept','comment':'Evidence checked'})
    assert accepted.status_code==200,accepted.text
    assert client.post(path,headers=reviewer,json={'action':'accept'}).status_code==409
    with application.state.session_factory() as db:
        record=db.get(SignRecord,record_id)
        assert record.status=='active' and record.expires_at-record.last_confirmed_at==timedelta(days=30)
        evidence=db.query(Evidence).one(); assert evidence.image_hash==image['sha256'] and evidence.uploaded_by==user['id']
        assert db.query(ConfirmationEvent).filter_by(action='confirm_existing').count()==1
    history=client.get(f'/api/v1/signs/{record_id}/history',headers=auth)
    assert history.status_code==200 and len(history.json()['items'])==1


def test_reject_report_preserves_record_and_private_images(client,application):
    record_id=add_sign(application); user,auth,image=user_and_image(client)
    created=report(client,auth,image,record_id,'report_removed'); assert created.status_code==201,created.text
    reviewer=headers(manager(client,application)['access_token'])
    response=client.post(f"/api/v1/manager/reports/{created.json()['id']}/review",headers=reviewer,json={'action':'reject'})
    assert response.status_code==200
    with application.state.session_factory() as db:
        assert db.get(SignRecord,record_id).status=='active' and db.query(Evidence).count()==0
    register(client,'bob'); bob=headers(login(client,'bob')['access_token'])
    assert client.get(image['content_url'],headers=bob).status_code==404
    assert report(client,bob,image,record_id).status_code==404


def test_stale_report_cannot_overwrite_a_newer_accepted_change(client,application):
    record_id=add_sign(application); user,auth,image=user_and_image(client)
    first=report(client,auth,image,record_id,'correct_class',proposed_class=9).json()
    second=report(client,auth,image,record_id,'report_removed').json()
    reviewer=headers(manager(client,application)['access_token'])
    assert client.post(f"/api/v1/manager/reports/{first['id']}/review",headers=reviewer,json={'action':'accept'}).status_code==200
    assert client.post(f"/api/v1/manager/reports/{second['id']}/review",headers=reviewer,json={'action':'accept'}).status_code==409
    with application.state.session_factory() as db:
        record=db.get(SignRecord,record_id); assert record.predicted_class==9 and record.status=='active'
        assert record.confidence==0 and record.is_uncertain


def test_admin_policy_is_audited_and_applies_to_new_acceptances(client,application):
    user,auth,image=user_and_image(client); admin=administrator(client,application); admin_auth=headers(admin['access_token'])
    assert client.patch('/api/v1/admin/policy',headers=auth,json={'confirmation_days':45}).status_code==403
    response=client.patch('/api/v1/admin/policy',headers=admin_auth,json={'confirmation_days':45})
    assert response.status_code==200,response.text
    assert client.get('/api/v1/policy',headers=auth).json()['confirmation_days']==45
    assert client.patch('/api/v1/admin/policy',headers=admin_auth,json={'confirmation_days':0}).status_code==422
    assert client.get('/api/v1/admin/policy/history',headers=admin_auth).json()['total']==1
    from test_images_observations import detect,submit
    from ai_engine.detection import Prediction
    run=detect(client,application,auth,image,[Prediction(0,.9,(1,2,30,40))])
    observations=submit(client,auth,image,run).json()
    accepted=client.post(f"/api/v1/manager/observations/{observations[0]['id']}/review",headers=admin_auth,json={'action':'accept'})
    assert accepted.status_code==200,accepted.text
    with application.state.session_factory() as db:
        sign=db.get(SignRecord,accepted.json()['sign_record_id'])
        assert sign.confirmation_days==45 and sign.expires_at-sign.last_confirmed_at==timedelta(days=45)


def test_legacy_report_keeps_the_existing_class_expiration_policy(client,application):
    from ai_engine.config import EXPIRATION_POLICIES
    record_id=add_sign(application,class_id=7)
    with application.state.session_factory() as db:
        sign=db.get(SignRecord,record_id); sign.confirmation_days=None; db.commit()
    user,auth,image=user_and_image(client)
    admin=headers(administrator(client,application)['access_token'])
    assert client.patch('/api/v1/admin/policy',headers=admin,json={'confirmation_days':45}).status_code==200
    row=report(client,auth,image,record_id).json()
    assert client.post(f"/api/v1/manager/reports/{row['id']}/review",headers=admin,json={'action':'accept'}).status_code==200
    with application.state.session_factory() as db:
        sign=db.get(SignRecord,record_id)
        assert sign.confirmation_days is None
        assert sign.expires_at-sign.last_confirmed_at==timedelta(days=EXPIRATION_POLICIES[sign.qcvn_code])


def test_expiry_job_is_idempotent_and_keeps_removed_records(application,client):
    from backend.app.services.lifecycle_service import expire_due_records
    stale=add_sign(application,expired=True); removed=add_sign(application,status='removed',expired=True)
    with application.state.session_factory() as db:
        assert expire_due_records(db)==1
        assert expire_due_records(db)==0
        assert db.get(SignRecord,stale).verification_status=='needs_confirmation'
        assert db.get(SignRecord,removed).status=='removed'


def test_running_api_expires_records_without_any_map_request(tmp_path):
    import time
    from fastapi.testclient import TestClient
    from backend.app.core.settings import Settings
    from backend.app.db.database import make_engine
    from backend.app.main import create_app
    engine=make_engine(f"sqlite:///{tmp_path/'scheduled.db'}")
    app=create_app(engine,Settings(lifecycle_interval_seconds=1,storage_root=tmp_path/'images'))
    try:
        with TestClient(app):
            record_id=add_sign(app,expired=True)
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                with app.state.session_factory() as db:
                    sign=db.get(SignRecord,record_id)
                    if sign.status=='expired':
                        assert sign.verification_status=='needs_confirmation'
                        break
                time.sleep(.05)
            else: raise AssertionError('Background expiry did not run without an API request')
    finally: engine.dispose()
