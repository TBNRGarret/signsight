"""Independent staff decisions contend against the same persisted sign revision."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.app.db.models import SignAudit,SignRecord,SignReport,Evidence,ConfirmationEvent
from test_accounts import headers,manager,login
from test_navigation_map import add_sign
from test_reports_policy import user_and_image,report


@pytest.mark.parametrize('same_report',[True,False])
def test_two_staff_publish_only_one_report_decision(client,application,same_report):
    record_id=add_sign(application)
    _,auth,image=user_and_image(client)
    first=report(client,auth,image,record_id,'report_removed').json()
    second=first if same_report else report(client,auth,image,record_id,'correct_class',proposed_class=5).json()
    actors=[headers(manager(client,application)['access_token']),headers(login(client,'owner')['access_token'])]
    barrier=Barrier(2)
    def accept(index):
        barrier.wait(timeout=10)
        row=[first,second][index]
        return client.post(f"/api/v1/manager/reports/{row['id']}/review",headers=actors[index],json={'action':'accept'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(accept,range(2)))
    assert sorted(statuses)==[200,409]
    with application.state.session_factory() as db:
        assert db.get(SignRecord,record_id).revision==1
        assert db.query(SignReport).filter_by(status='accepted').count()==1
        assert db.query(Evidence).count()==db.query(ConfirmationEvent).count()==db.query(SignAudit).count()==1
        if not same_report:assert db.query(SignReport).filter_by(status='pending').count()==1
