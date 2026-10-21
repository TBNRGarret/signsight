"""Review evidence-backed changes against the sign revision observed at submission."""
import json
from datetime import datetime
from fastapi import HTTPException
from ai_engine.config import CLASS_MAPPING
from backend.app.db.models import SignReport,SignRecord,UploadedImage,Evidence,ConfirmationEvent,SignAudit


def snapshot(record):
    fields=('predicted_class','qcvn_code','name_vi','confidence','is_uncertain','latitude','longitude','location_source',
            'status','verification_status','confirmation_days','revision','merged_into_id','last_confirmed_at','expires_at')
    return {field:(value.isoformat() if isinstance(value,datetime) else value) for field in fields for value in [getattr(record,field)]}


def audit(db,record,actor_id,action,before,report_id=None):
    db.add(SignAudit(record_id=record.id,report_id=report_id,actor_id=actor_id,action=action,
                    before_json=json.dumps(before,ensure_ascii=False),after_json=json.dumps(snapshot(record),ensure_ascii=False)))


def review_report(db,report_id,payload,reviewer,store):
    actor=reviewer.id; db.rollback()
    status='accepted' if payload.action=='accept' else 'rejected'; now=datetime.utcnow()
    claimed=db.query(SignReport).filter(SignReport.id==report_id,SignReport.status=='pending').update(
        {'status':status,'reviewed_by':actor,'reviewed_at':now,'review_comment':payload.comment},synchronize_session=False)
    if claimed!=1:
        exists=db.get(SignReport,report_id) is not None; db.rollback()
        raise HTTPException(409 if exists else 404,'Report has already been reviewed' if exists else 'Report not found')
    report=db.get(SignReport,report_id)
    if status=='accepted':
        record=db.get(SignRecord,report.record_id); before=snapshot(record)
        claim=db.query(SignRecord).filter(SignRecord.id==report.record_id,SignRecord.revision==report.base_revision).update(
            {SignRecord.revision:SignRecord.revision+1},synchronize_session=False)
        if claim!=1:
            db.rollback(); raise HTTPException(409,'Sign changed since this report; review the latest evidence before resubmitting')
        image=db.get(UploadedImage,report.image_id)
        store.read(image.storage_key,image.sha256)
        db.refresh(record)
        action=report.action
        if action=='report_removed':
            record.status='removed'; record.verification_status='current'
        elif action=='report_damaged':
            record.status='pending_revalidation'; record.verification_status='needs_confirmation'
        else:
            record.status='active'; record.verification_status='current'
            record.last_confirmed_at=now
            if action=='correct_class':
                info=CLASS_MAPPING[report.proposed_class]
                record.predicted_class=report.proposed_class; record.qcvn_code=info['qcvn_code']; record.name_vi=info['name_vi']
                record.confidence=0; record.is_uncertain=True
            elif action=='correct_location':
                record.latitude=report.latitude; record.longitude=report.longitude; record.location_source='user_confirmed'
            from backend.app.services.lifecycle_service import calculate_expiration_date
            record.expires_at=calculate_expiration_date(record.qcvn_code,now,record.confirmation_days)
        evidence=Evidence(record_id=record.id,image_url=f'/api/v1/images/{image.id}/content',image_hash=image.sha256,
                          file_size_bytes=image.size_bytes,uploaded_by=report.created_by)
        db.add(evidence); db.flush()
        db.add(ConfirmationEvent(record_id=record.id,action=action,comment=report.comment,evidence_id=evidence.id,confirmed_by=actor,created_at=now))
        audit(db,record,actor,action,before,report.id)
    db.commit(); db.refresh(report); return report
