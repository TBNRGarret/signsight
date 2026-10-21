from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.app.db.models import SignRecord, ConfirmationEvent
from ai_engine.config import EXPIRATION_POLICIES

def calculate_expiration_date(qcvn_code: str, base_time: Optional[datetime] = None, confirmation_days: Optional[int] = None) -> datetime:
    if base_time is None:
        base_time = datetime.utcnow()
    days = confirmation_days if confirmation_days is not None else EXPIRATION_POLICIES.get(qcvn_code, 180)
    return base_time + timedelta(days=days)

def check_and_update_lifecycle_status(db: Session):
    """
    Background job or query-time check to transition records from active -> pending_revalidation -> expired.
    """
    return expire_due_records(db)


def expire_due_records(db:Session,now=None):
    db.rollback()
    changed=db.query(SignRecord).filter(SignRecord.status=='active',SignRecord.expires_at<=(now or datetime.utcnow())).update(
        {SignRecord.status:'expired',SignRecord.verification_status:'needs_confirmation'},synchronize_session=False)
    db.commit()
    return changed

def process_revalidation(
    db: Session,
    record_id: str,
    action: str,
    comment: Optional[str] = None,
    confirmed_by: Optional[str] = None,
) -> SignRecord:
    record = db.query(SignRecord).filter(SignRecord.id == record_id).first()
    if not record:
        raise ValueError(f"Sign record {record_id} not found")
    if record.merged_into_id:
        raise HTTPException(409, "Sign merged; review the linked current record")

    now = datetime.utcnow()
    before=None
    if confirmed_by:
        from backend.app.services.report_service import snapshot,audit
        before=snapshot(record)
    record.revision+=1
    evidence_id = None

    if action == "confirm_existing":
        record.status = "active"
        record.last_confirmed_at = now
        record.expires_at = calculate_expiration_date(record.qcvn_code, now, record.confirmation_days)
        record.verification_status = "current"
    elif action == "report_removed":
        record.status = "removed"
        record.verification_status = "current"
    elif action == "report_damaged":
        record.status = "pending_revalidation"
        record.verification_status = "needs_confirmation"

    event = ConfirmationEvent(
        record_id=record.id,
        action=action,
        comment=comment,
        evidence_id=evidence_id,
        confirmed_by=confirmed_by,
        created_at=now
    )
    db.add(event)
    if before is not None:
        audit(db,record,confirmed_by,action,before)
    db.commit()
    db.refresh(record)
    return record
