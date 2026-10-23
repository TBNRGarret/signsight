"""Bounded, global staff catalogue and work counts; independent of map viewport."""
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from backend.app.core.security import require_roles
from backend.app.db.database import get_db
from backend.app.db.models import SignRecord, Observation, SignReport, DuplicateCandidate
from backend.app.schemas.sign import SignRecordResponse
from backend.app.services.lifecycle_service import check_and_update_lifecycle_status

router = APIRouter()

@router.get('/manager/summary')
def summary(response: Response, user=Depends(require_roles('manager', 'admin')), db: Session=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {
        'contributions': db.query(Observation).filter(Observation.status == 'pending').count(),
        'reports': db.query(SignReport).filter(SignReport.status == 'pending').count(),
        'duplicates': db.query(DuplicateCandidate).filter(DuplicateCandidate.status == 'pending_review').count(),
        'signs': db.query(SignRecord).count(),
    }

@router.get('/manager/signs')
def catalogue(response: Response, q: str=Query('', max_length=100),
              status: Literal['active','expired','pending_revalidation','removed'] | None=None,
              verification_status: Literal['unverified','current','needs_confirmation'] | None=None,
              offset: int=Query(0, ge=0), limit: int=Query(25, ge=1, le=100),
              user=Depends(require_roles('manager','admin')), db: Session=Depends(get_db)):
    check_and_update_lifecycle_status(db)
    query = db.query(SignRecord)
    if term := q.strip():
        query = query.filter(or_(SignRecord.id.contains(term, autoescape=True),
                                 func.lower(SignRecord.qcvn_code).contains(term.lower(), autoescape=True),
                                 func.lower(SignRecord.name_vi).contains(term.lower(), autoescape=True)))
    if status is not None:
        query = query.filter(SignRecord.status == status)
    if verification_status is not None:
        query = query.filter(SignRecord.verification_status == verification_status)
    total = query.count()
    records = query.order_by(SignRecord.created_at.desc(), SignRecord.id).offset(offset).limit(limit).all()
    response.headers['Cache-Control'] = 'no-store'
    return {'items': [SignRecordResponse.model_validate(row) for row in records],
            'total': total, 'offset': offset, 'limit': limit}
