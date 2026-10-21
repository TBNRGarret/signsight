from typing import List
from sqlalchemy.orm import Session
from backend.app.db.models import SignRecord, DuplicateCandidate
from backend.app.services.geo_service import haversine_distance_meters
from ai_engine.config import DUPLICATE_DISTANCE_THRESHOLD_METERS

def check_and_create_duplicate_candidates(
    db: Session,
    new_record: SignRecord,
    threshold_meters: float = DUPLICATE_DISTANCE_THRESHOLD_METERS
) -> List[DuplicateCandidate]:
    """
    Checks nearby existing active sign records within threshold_meters.
    If a nearby observation exists, flags it as a duplicate candidate.
    DOES NOT automatically merge - preserves reviewability.
    """
    # Rough bounding box filter (~0.001 deg is ~111m) to avoid scanning entire table
    lat_delta = (threshold_meters * 1.5) / 111000.0
    lon_delta = (threshold_meters * 1.5) / 111000.0

    candidates_query = db.query(SignRecord).filter(
        SignRecord.id != new_record.id,
        SignRecord.status.in_(["active", "pending_revalidation"]),
        SignRecord.latitude.between(new_record.latitude - lat_delta, new_record.latitude + lat_delta),
        SignRecord.longitude.between(new_record.longitude - lon_delta, new_record.longitude + lon_delta)
    )

    created_candidates = []
    for existing in candidates_query.all():
        dist = haversine_distance_meters(
            new_record.latitude, new_record.longitude,
            existing.latitude, existing.longitude
        )

        if dist <= threshold_meters:
            class_match = (new_record.predicted_class == existing.predicted_class)
            # Similarity score: high when close & matching class
            similarity = (1.0 - (dist / threshold_meters)) * (1.0 if class_match else 0.5)

            candidate = DuplicateCandidate(
                new_record_id=new_record.id,
                existing_record_id=existing.id,
                distance_meters=round(dist, 2),
                class_match=class_match,
                similarity_score=round(similarity, 3),
                status="pending_review"
            )
            db.add(candidate)
            created_candidates.append(candidate)

    if created_candidates:
        db.flush()  # The caller commits the record, evidence and candidates atomically.

    return created_candidates
