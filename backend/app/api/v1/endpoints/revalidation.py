from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.security import require_roles

from backend.app.db.database import get_db
from backend.app.db.models import SignRecord, DuplicateCandidate, User
from backend.app.schemas.sign import (
    RevalidationRequest,
    SignRecordResponse,
)
from backend.app.services.lifecycle_service import (
    process_revalidation,
    check_and_update_lifecycle_status
)

router = APIRouter()

@router.post("/{record_id}", response_model=SignRecordResponse)
def submit_revalidation(
    record_id: str,
    payload: RevalidationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("manager", "admin")),
):
    """
    Submits a revalidation action:
    - 'confirm_existing': Sign still exists. Extends expiration date.
    - 'report_removed': Sign has been removed. Marks status as 'removed'.
    - 'report_damaged': Sign is damaged/altered. Marks as 'pending_revalidation' / uncertain.
    """
    try:
        updated = process_revalidation(
            db=db,
            record_id=record_id,
            action=payload.action,
            comment=payload.comment,
            confirmed_by=user.id,
        )
        return SignRecordResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/pending", response_model=List[SignRecordResponse])
def get_pending_revalidation_signs(db: Session = Depends(get_db), user: User = Depends(require_roles("manager", "admin"))):
    """
    Returns all sign records that are expired or pending confirmation.
    """
    check_and_update_lifecycle_status(db)
    pending_records = db.query(SignRecord).filter(
        SignRecord.status.in_(["pending_revalidation", "expired"])
    ).all()
    return [SignRecordResponse.model_validate(r) for r in pending_records]

@router.get("/duplicates")
def get_duplicate_candidates(db: Session = Depends(get_db), user: User = Depends(require_roles("manager", "admin"))):
    """
    Returns pending duplicate candidate pairs.
    """
    candidates = db.query(DuplicateCandidate).filter(
        DuplicateCandidate.status == "pending_review"
    ).all()

    results = []
    for c in candidates:
        new_rec = db.query(SignRecord).filter(SignRecord.id == c.new_record_id).first()
        old_rec = db.query(SignRecord).filter(SignRecord.id == c.existing_record_id).first()
        results.append({
            "candidate_id": c.id,
            "distance_meters": c.distance_meters,
            "class_match": c.class_match,
            "similarity_score": c.similarity_score,
            "status": c.status,
            "new_record": SignRecordResponse.model_validate(new_rec) if new_rec else None,
            "existing_record": SignRecordResponse.model_validate(old_rec) if old_rec else None
        })
    return results
