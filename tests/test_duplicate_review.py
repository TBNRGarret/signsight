from backend.app.db.models import DuplicateCandidate,SignRecord,SignAudit
from test_accounts import register,login,headers,manager
from test_navigation_map import add_sign


def candidate(application,source,target):
    with application.state.session_factory() as db:
        row=DuplicateCandidate(new_record_id=source,existing_record_id=target,distance_meters=10,class_match=True,status='pending_review')
        db.add(row); db.commit(); return row.id


def test_merge_preserves_records_audit_and_only_manager_can_review(client,application):
    source=add_sign(application,lat=10.7801); target=add_sign(application)
    pair=candidate(application,source,target)
    register(client); user=headers(login(client)['access_token'])
    path=f'/api/v1/manager/duplicates/{pair}/review'
    assert client.post(path,headers=user,json={'action':'merge'}).status_code==403
    reviewer=headers(manager(client,application)['access_token'])
    response=client.post(path,headers=reviewer,json={'action':'merge'})
    assert response.status_code==200,response.text
    assert client.post(path,headers=reviewer,json={'action':'merge'}).status_code==409
    with application.state.session_factory() as db:
        assert db.query(SignRecord).count()==2
        assert db.get(SignRecord,source).merged_into_id==target and db.get(SignRecord,source).status=='removed'
        assert db.get(SignRecord,target).status=='active'
        assert db.query(SignAudit).count()==2
    response=client.post(f'/api/v1/revalidation/{source}',headers=reviewer,json={'action':'confirm_existing'})
    assert response.status_code==409
    with application.state.session_factory() as db:
        assert db.get(SignRecord,source).status=='removed'


def test_merged_proof_is_visible_on_target_and_older_reports_stay_pending(client,application):
    from test_reports_policy import user_and_image,report
    source=add_sign(application,lat=10.7801); target=add_sign(application)
    user,auth,image=user_and_image(client)
    reviewer=headers(manager(client,application)['access_token'])
    proof=report(client,auth,image,source).json()
    assert client.post(f"/api/v1/manager/reports/{proof['id']}/review",headers=reviewer,json={'action':'accept'}).status_code==200
    stale=report(client,auth,image,source,'report_removed').json()
    pair=candidate(application,source,target)
    assert client.post(f'/api/v1/manager/duplicates/{pair}/review',headers=reviewer,json={'action':'merge'}).status_code==200
    detail=client.get(f'/api/v1/signs/{target}',headers=auth).json()
    assert len(detail['evidence'])==1 and detail['evidence'][0]['sha256']==image['sha256']
    assert client.get(detail['evidence'][0]['content_url'],headers=auth).status_code==200
    assert client.post(f"/api/v1/manager/reports/{stale['id']}/review",headers=reviewer,json={'action':'accept'}).status_code==409
    assert client.get(f"/api/v1/reports/{stale['id']}",headers=auth).json()['status']=='pending'
    assert report(client,auth,image,source).status_code==409


def test_merge_rejects_different_classes_and_dismiss_does_not_remove(client,application):
    source=add_sign(application,class_id=9); target=add_sign(application)
    pair=candidate(application,source,target); reviewer=headers(manager(client,application)['access_token'])
    path=f'/api/v1/manager/duplicates/{pair}/review'
    assert client.post(path,headers=reviewer,json={'action':'merge'}).status_code==409
    assert client.post(path,headers=reviewer,json={'action':'dismiss'}).status_code==200
    with application.state.session_factory() as db:
        assert db.get(SignRecord,source).status=='active'
