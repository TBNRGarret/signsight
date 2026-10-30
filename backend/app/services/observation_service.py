"""Server-owned inference and atomic moderation; original predictions are never edited."""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ai_engine.config import CONFIDENCE_THRESHOLD
from ai_engine.catalog import DEFAULT_CATALOG
from backend.app.db.models import (
    UploadedImage, InferenceRun, ImageDetection, Observation, SignRecord, Evidence, ConfirmationEvent, SignReport,
)
from backend.app.schemas.images import BoundingBox, DetectionResponse, RunResponse, ObservationResponse
from backend.app.services.duplicate_service import check_and_create_duplicate_candidates


def authorized_image(db, image_id, user, owner_only=False):
    image = db.get(UploadedImage, image_id)
    if image is None:
        raise HTTPException(404, "Image not found")
    if image.uploaded_by == user.id:
        return image
    if not owner_only:
        submitted = db.query(Observation).join(ImageDetection).join(InferenceRun).filter(
            InferenceRun.image_id == image_id,
        )
        if submitted.filter(Observation.status == "accepted").first() is not None:
            return image
        if user.role in ("manager", "admin") and submitted.first() is not None:
            return image
        reports=db.query(SignReport).filter(SignReport.image_id==image_id)
        if reports.filter(SignReport.status=='accepted').first() is not None:
            return image
        if user.role in ('manager','admin') and reports.first() is not None:
            return image
    raise HTTPException(404, "Image not found")


def detection_response(detection, catalog=DEFAULT_CATALOG):
    info = catalog.by_id[detection.predicted_class]
    bbox = None if detection.x1 is None else BoundingBox(
        x1=detection.x1, y1=detection.y1, x2=detection.x2, y2=detection.y2,
    )
    return DetectionResponse(
        id=detection.id, predicted_class=detection.predicted_class,
        model_class_id=detection.model_class_id,
        qcvn_code=info["qcvn_code"], name_vi=info["name_vi"], confidence=detection.confidence,
        is_uncertain=detection.confidence < CONFIDENCE_THRESHOLD, bbox=bbox,
    )


def run_response(run, catalog=DEFAULT_CATALOG):
    return RunResponse(
        id=run.id, image_id=run.image_id, engine=run.engine,
        task="detection" if run.engine == "yolo" else "classification",
        model_version=run.model_version, created_at=run.created_at,
        mapping_sha256=run.mapping_sha256,catalog_sha256=run.catalog_sha256,
        detections=[detection_response(item,catalog) for item in run.detections],
    )


def observation_response(observation, catalog=DEFAULT_CATALOG):
    run = observation.detection.run
    proposed=catalog.by_id.get(observation.proposed_class)
    return ObservationResponse(
        id=observation.id, image_id=run.image_id, detection=detection_response(observation.detection,catalog),
        engine=run.engine, model_version=run.model_version, created_by=observation.created_by,
        latitude=observation.latitude, longitude=observation.longitude,
        location_source=observation.location_source, proposed_class=observation.proposed_class,
        proposed_qcvn_code=proposed['qcvn_code'] if proposed else None,
        proposed_name_vi=proposed['name_vi'] if proposed else None,
        correction_reason=observation.correction_reason, status=observation.status,
        created_at=observation.created_at, reviewed_by=observation.reviewed_by,
        reviewed_at=observation.reviewed_at, review_comment=observation.review_comment,
        sign_record_id=observation.sign_record_id,
    )


def persist_run(db, image, engine, result, catalog=DEFAULT_CATALOG):
    # Validate adapter output before writing. Malformed results never become observations.
    import math
    if len(result.predictions) > 25 or not result.model_version or len(result.model_version) > 100:
        raise HTTPException(503, "Invalid inference result")
    rows = []
    for ordinal, prediction in enumerate(result.predictions):
        if type(prediction.predicted_class) is not int or prediction.predicted_class not in catalog.by_id or not math.isfinite(prediction.confidence) or not 0 <= prediction.confidence <= 1:
            raise HTTPException(503, "Invalid inference result")
        coordinates = dict(x1=None, y1=None, x2=None, y2=None)
        if engine == "yolo":
            if prediction.bbox is None:
                raise HTTPException(503, "Detector did not return a bounding box")
            try:
                box = BoundingBox(x1=prediction.bbox[0], y1=prediction.bbox[1], x2=prediction.bbox[2], y2=prediction.bbox[3])
            except (ValueError, IndexError, TypeError):
                raise HTTPException(503, "Detector returned an invalid bounding box") from None
            if box.x2 > image.width or box.y2 > image.height:
                raise HTTPException(503, "Detector returned an out-of-bounds box")
            coordinates = box.model_dump()
        rows.append(ImageDetection(ordinal=ordinal, predicted_class=prediction.predicted_class,
                                   model_class_id=getattr(prediction,'model_class_id',None),
                                   confidence=prediction.confidence, **coordinates))
    import re
    mapping_hash=getattr(result,'mapping_sha256',None)
    catalog_hash=getattr(result,'catalog_sha256',None)
    if (any(value is not None and (not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value))
            for value in (mapping_hash,catalog_hash)) or
        catalog_hash is not None and catalog_hash!=catalog.sha256 or
        any(row.model_class_id is not None and (type(row.model_class_id) is not int or row.model_class_id<0) for row in rows)):
        raise HTTPException(503,'Invalid inference provenance')
    run = InferenceRun(image_id=image.id, engine=engine, model_version=result.model_version, detections=rows,
                       mapping_sha256=mapping_hash,catalog_sha256=catalog_hash)
    db.rollback()  # Release the read snapshot held during inference before starting a write.
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def review_observation(db: Session, observation_id, payload, reviewer, confirmation_days, catalog=DEFAULT_CATALOG):
    reviewer_id = reviewer.id
    db.rollback()  # SQLite writers must not upgrade a stale auth/read snapshot.
    now = datetime.utcnow()
    status = "accepted" if payload.action == "accept" else "rejected"
    claimed = db.query(Observation).filter(Observation.id == observation_id, Observation.status == "pending").update(
        {Observation.status: status, Observation.reviewed_by: reviewer_id,
         Observation.reviewed_at: now, Observation.review_comment: payload.comment}, synchronize_session=False,
    )
    if claimed != 1:
        exists = db.get(Observation, observation_id) is not None
        db.rollback()
        raise HTTPException(409 if exists else 404, "Observation has already been reviewed" if exists else "Observation not found")
    observation = db.get(Observation, observation_id)
    if status == "accepted":
        detection = observation.detection
        image = db.get(UploadedImage, detection.run.image_id)
        class_id = observation.proposed_class if observation.proposed_class is not None else detection.predicted_class
        corrected = class_id != detection.predicted_class
        if class_id not in catalog.by_id:
            db.rollback(); raise HTTPException(409,'Contribution catalog entry is unavailable; restore the configured catalog')
        info = catalog.by_id[class_id]
        record = SignRecord(
            predicted_class=class_id, qcvn_code=info["qcvn_code"], name_vi=info["name_vi"],
            confidence=0.0 if corrected else detection.confidence,
            is_uncertain=corrected or detection.confidence < CONFIDENCE_THRESHOLD,
            latitude=observation.latitude, longitude=observation.longitude,
            location_source=observation.location_source, created_by=observation.created_by,
            status="active", verification_status="current", confirmation_days=confirmation_days,
            created_at=now, last_confirmed_at=now, expires_at=now + timedelta(days=confirmation_days),
        )
        db.add(record)
        db.flush()
        evidence = Evidence(
            record_id=record.id, image_url=f"/api/v1/images/{image.id}/content",
            image_hash=image.sha256, file_size_bytes=image.size_bytes, uploaded_by=image.uploaded_by,
        )
        db.add(evidence)
        db.flush()
        db.add(ConfirmationEvent(record_id=record.id, action="accept_observation", evidence_id=evidence.id,
                                 confirmed_by=reviewer_id, comment=payload.comment, created_at=now))
        observation.sign_record_id = record.id
        check_and_create_duplicate_candidates(db, record)
    db.commit()
    db.refresh(observation)
    return observation
