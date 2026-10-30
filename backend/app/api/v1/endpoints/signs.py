import uuid
from fastapi import Request
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.security import get_current_user, require_roles

from backend.app.db.database import get_db
from backend.app.db.models import SignRecord, DuplicateCandidate, User
from backend.app.schemas.sign import (
    InferenceResponse,
    SignRecordCreate,
    SignRecordResponse
)
from ai_engine.inference import classifier
from backend.app.services.duplicate_service import check_and_create_duplicate_candidates
from backend.app.services.lifecycle_service import calculate_expiration_date, check_and_update_lifecycle_status
from backend.app.services.image_store import sanitize_image
from backend.app.core.catalog import require_catalog_id

router = APIRouter()

@router.post("/classify", response_model=InferenceResponse)
async def classify_sign_image(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """
    Accepts an image file and runs AI inference.
    Returns predicted Vietnam traffic sign class, confidence, and uncertainty flag.
    """
    chunks, size = [], 0
    try:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > request.app.state.settings.max_upload_bytes:
                raise HTTPException(413, "Image exceeds upload size limit")
            chunks.append(chunk)
        image = sanitize_image(b"".join(chunks),file.content_type,request.app.state.settings.max_image_pixels)
        if classifier.model is None:
            raise HTTPException(503, "CNN checkpoint unavailable")
        return classifier.predict(image.data)
    finally:
        await file.close()

@router.post("/register", response_model=SignRecordResponse, deprecated=True)
def register_sign_record(
    payload: SignRecordCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("manager", "admin")),
):
    """
    Registers a new georeferenced traffic sign observation.
    Automatically calculates expiration date, checks for duplicates, and creates DB record.
    """
    from ai_engine.config import CONFIDENCE_THRESHOLD

    class_info = require_catalog_id(request.app.state.catalog,payload.predicted_class)

    qcvn_code = class_info["qcvn_code"]
    name_vi = class_info["name_vi"]
    is_uncertain = (payload.confidence < CONFIDENCE_THRESHOLD)
    expires_at = calculate_expiration_date(qcvn_code)

    new_record = SignRecord(
        id=str(uuid.uuid4()),
        predicted_class=payload.predicted_class,
        qcvn_code=qcvn_code,
        name_vi=name_vi,
        confidence=round(payload.confidence, 4),
        is_uncertain=is_uncertain,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_source=payload.location_source or "user_confirmed",
        status="active",
        expires_at=expires_at,
        created_by=user.id
    )
    db.add(new_record)
    db.flush()

    # Duplicate observation check
    duplicate_candidates = check_and_create_duplicate_candidates(db, new_record)
    db.commit()
    db.refresh(new_record)

    response_data = SignRecordResponse.model_validate(new_record)
    response_data.possible_duplicate_count = len(duplicate_candidates)
    return response_data

@router.get("", response_model=List[SignRecordResponse])
def list_sign_records(
    status: Optional[str] = Query(None, description="Filter by status ('active', 'expired', 'removed')"),
    is_uncertain: Optional[bool] = Query(None, description="Filter by uncertainty flag"),
    qcvn_code: Optional[str] = Query(None, description="Filter by QCVN code"),
    db: Session = Depends(get_db)
):
    """
    Returns traffic sign records with optional filters.
    """
    check_and_update_lifecycle_status(db)
    query = db.query(SignRecord)

    if status:
        query = query.filter(SignRecord.status == status)
    if is_uncertain is not None:
        query = query.filter(SignRecord.is_uncertain == is_uncertain)
    if qcvn_code:
        query = query.filter(SignRecord.qcvn_code == qcvn_code)

    records = query.all()
    results = []
    for r in records:
        resp = SignRecordResponse.model_validate(r)
        resp.possible_duplicate_count = db.query(DuplicateCandidate).filter(
            (DuplicateCandidate.new_record_id == r.id) | (DuplicateCandidate.existing_record_id == r.id)
        ).count()
        results.append(resp)

    return results
