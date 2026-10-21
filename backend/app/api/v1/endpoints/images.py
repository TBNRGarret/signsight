import io
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_engine.detection import DetectionResult, DetectorUnavailable, Prediction
from ai_engine.inference import classifier
from backend.app.core.security import get_current_user, require_roles
from backend.app.db.database import get_db
from backend.app.db.models import UploadedImage, InferenceRun, ImageDetection, Observation, User
from backend.app.schemas.images import ImageResponse, RunResponse, ObservationBatch, ObservationResponse, ObservationPage, ObservationReview
from backend.app.services.image_store import sanitize_image
from backend.app.services.observation_service import authorized_image, persist_run, run_response, observation_response, review_observation
from backend.app.services.policy_service import confirmation_days
from backend.app.services.evidence_service import sign_evidence

router = APIRouter()


def image_response(image, user):
    return ImageResponse(
        id=image.id, width=image.width, height=image.height, size_bytes=image.size_bytes, sha256=image.sha256,
        content_url=f"/api/v1/images/{image.id}/content", created_at=image.created_at,
        exif_latitude=image.exif_latitude if image.uploaded_by == user.id else None,
        exif_longitude=image.exif_longitude if image.uploaded_by == user.id else None,
    )


@router.post("/images", response_model=ImageResponse, status_code=201)
async def upload_image(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = request.app.state.settings
    chunks, size = [], 0
    try:
        while chunk := await file.read(64 * 1024):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise HTTPException(413, "Image exceeds upload size limit")
            chunks.append(chunk)
        sanitized = sanitize_image(b"".join(chunks), file.content_type, settings.max_image_pixels)
    finally:
        await file.close()
    image_id = str(uuid.uuid4())
    key = image_id + ".jpg"
    store = request.app.state.image_store
    image = UploadedImage(id=image_id, uploaded_by=user.id, storage_key=key,
                          sha256=sanitized.sha256, size_bytes=len(sanitized.data),
                          width=sanitized.width, height=sanitized.height,
                          exif_latitude=sanitized.latitude, exif_longitude=sanitized.longitude)
    db.rollback()  # Release auth reads before the file/DB write transaction.
    saved = False
    try:
        store.save(key, sanitized.data)
        saved = True
        db.add(image)
        db.commit()
    except Exception:
        db.rollback()
        if saved:
            store.remove(key)
        raise
    db.refresh(image)
    return image_response(image, user)


@router.get("/images/{image_id}", response_model=ImageResponse)
def get_image(image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return image_response(authorized_image(db, image_id, user), user)


@router.get("/images/{image_id}/content")
def image_content(image_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    image = authorized_image(db, image_id, user)
    data = request.app.state.image_store.read(image.storage_key, image.sha256)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/images/{image_id}/detect", response_model=RunResponse)
def detect(image_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    image = authorized_image(db, image_id, user, owner_only=True)
    data = request.app.state.image_store.read(image.storage_key, image.sha256)
    db.expunge(image)
    db.rollback()  # A GPU inference must not hold a SQLite read lock.
    try:
        with Image.open(io.BytesIO(data)) as source:
            result = request.app.state.detector.predict(source.convert("RGB"))
        return run_response(persist_run(db, image, "yolo", result))
    except DetectorUnavailable as error:
        raise HTTPException(503, str(error)) from error


@router.post("/images/{image_id}/classify", response_model=RunResponse)
def classify(image_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    image = authorized_image(db, image_id, user, owner_only=True)
    if classifier.model is None:
        raise HTTPException(503, "CNN checkpoint unavailable; simulated predictions cannot be submitted")
    data = request.app.state.image_store.read(image.storage_key, image.sha256)
    db.expunge(image)
    db.rollback()
    prediction = classifier.predict(data)
    result = DetectionResult(classifier.model_version, [Prediction(prediction["predicted_class"], prediction["confidence"], None)])
    return run_response(persist_run(db, image, "cnn", result))


@router.get("/ai/status")
def ai_status(request: Request, user: User = Depends(get_current_user)):
    return {"cnn": {"ready": classifier.model is not None, "task": "cropped_image_classification"},
            "yolo": request.app.state.detector.status()}


@router.get("/inference-runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.get(InferenceRun, run_id)
    if run is None:
        raise HTTPException(404, "Inference run not found")
    image = authorized_image(db, run.image_id, user)
    if image.uploaded_by != user.id:
        # A public image does not make other private inference attempts public.
        submitted = db.query(Observation).join(ImageDetection).filter(ImageDetection.run_id == run_id)
        if user.role not in ("manager", "admin") or submitted.first() is None:
            raise HTTPException(404, "Inference run not found")
    return run_response(run)


@router.post("/observations", response_model=list[ObservationResponse], status_code=201)
def submit(payload: ObservationBatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    image = authorized_image(db, payload.image_id, user, owner_only=True)
    rows = []
    for item in payload.items:
        detection = db.get(ImageDetection, item.detection_id)
        if detection is None or detection.run.image_id != image.id:
            raise HTTPException(404, "Detection does not belong to this image")
        if item.proposed_class is not None and item.proposed_class != detection.predicted_class and not (item.correction_reason or "").strip():
            raise HTTPException(422, "A class correction requires a reason")
        rows.append(Observation(created_by=user.id, **item.model_dump()))
    try:
        db.rollback()  # End validation reads before the atomic insertion.
        db.add_all(rows)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "A detection has already been submitted") from error
    return [observation_response(row) for row in rows]


def observation_page(query, offset, limit):
    return ObservationPage(items=[observation_response(row) for row in query.order_by(Observation.created_at.desc(), Observation.id).offset(offset).limit(limit)],
                           total=query.count(), offset=offset, limit=limit)


@router.get("/me/observations", response_model=ObservationPage)
def own_observations(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                     status: Literal["pending", "accepted", "rejected"] | None = Query(None),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Observation).filter(Observation.created_by == user.id)
    if status is not None:
        query = query.filter(Observation.status == status)
    return observation_page(query, offset, limit)


@router.get("/manager/observations", response_model=ObservationPage)
def pending_observations(status: Literal["pending", "accepted", "rejected"] = "pending", offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                         user: User = Depends(require_roles("manager", "admin")), db: Session = Depends(get_db)):
    return observation_page(db.query(Observation).filter(Observation.status == status), offset, limit)


@router.get("/observations/{observation_id}", response_model=ObservationResponse)
def get_observation(observation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    observation = db.get(Observation, observation_id)
    if observation is None or (observation.created_by != user.id and user.role not in ("manager", "admin")):
        raise HTTPException(404, "Observation not found")
    return observation_response(observation)


@router.post("/manager/observations/{observation_id}/review", response_model=ObservationResponse)
def review(observation_id: str, payload: ObservationReview, request: Request,
           user: User = Depends(require_roles("manager", "admin")), db: Session = Depends(get_db)):
    days=confirmation_days(db,request.app.state.settings.confirmation_days)
    return observation_response(review_observation(db, observation_id, payload, user, days))


@router.get("/signs/{record_id}/evidence")
def evidence(record_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": row.id, "content_url": row.image_url, "sha256": row.image_hash,
             "size_bytes": row.file_size_bytes, "created_at": row.created_at}
            for row in sign_evidence(db,record_id)]
