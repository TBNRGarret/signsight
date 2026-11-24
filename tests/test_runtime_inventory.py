from datetime import datetime, timedelta
import os
import uuid

from backend.app.db.models import UploadedImage
from test_images_observations import owner, upload, detect, submit, picture
from test_navigation_map import add_sign
from test_reports_policy import report


def test_inventory_is_read_only_and_preserves_contribution_and_report_evidence(client, application, tmp_path):
    from backend.app.services.runtime_inventory import inventory_runtime
    auth = owner(client)
    contribution, proof, abandoned, recent = [upload(client, auth, picture(size=(110+i,80))) for i in range(4)]
    assert submit(client,auth,contribution,detect(client,application,auth,contribution)).status_code == 201
    assert report(client,auth,proof,add_sign(application)).status_code == 201
    cutoff = datetime.utcnow() - timedelta(days=40)
    with application.state.session_factory() as db:
        engine = db.get_bind()
        for image in (contribution,proof,abandoned): db.get(UploadedImage,image['id']).created_at = cutoff
        db.commit()
    root = application.state.image_store.root
    stray = root/(str(uuid.uuid4())+'.jpg');stray.write_bytes(b'untracked')
    os.utime(stray,(cutoff.timestamp(),cutoff.timestamp()))
    before = {p.name:p.read_bytes() for p in root.iterdir()}
    result = inventory_runtime(engine,root,verify_images=True)
    assert result['read_only'] is True
    assert result['database']['integrity'] == 'ok'
    assert result['database']['foreign_key_violations'] == []
    assert [r['id'] for r in result['unused_upload_candidates']] == [abandoned['id']]
    assert result['protected_images'] == 2
    assert result['untracked_files'][0]['name'] == stray.name
    assert result['untracked_files'][0]['old_enough'] is True
    assert result['missing_images'] == result['invalid_images'] == []
    assert {p.name:p.read_bytes() for p in root.iterdir()} == before
    with application.state.session_factory() as db: assert db.query(UploadedImage).count() == 4


def test_inventory_reports_missing_and_corrupt_images_without_removing_rows(client, application):
    from backend.app.services.runtime_inventory import inventory_runtime
    auth = owner(client)
    missing, corrupt = upload(client,auth),upload(client,auth)
    with application.state.session_factory() as db:
        engine=db.get_bind()
        keys={r.id:r.storage_key for r in db.query(UploadedImage)}
    store=application.state.image_store
    store.path(keys[missing['id']]).unlink()
    store.path(keys[corrupt['id']]).write_bytes(b'corrupt')
    result=inventory_runtime(engine,store.root,verify_images=True)
    assert result['missing_images'] == [missing['id']]
    assert result['invalid_images'] == [corrupt['id']]
    with application.state.session_factory() as db: assert db.query(UploadedImage).count()==2
