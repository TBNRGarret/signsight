from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageResponse(BaseModel):
    id: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    content_url: str
    exif_latitude: float | None
    exif_longitude: float | None
    created_at: datetime


class BoundingBox(BaseModel):
    x1: float = Field(ge=0, allow_inf_nan=False)
    y1: float = Field(ge=0, allow_inf_nan=False)
    x2: float = Field(gt=0, allow_inf_nan=False)
    y2: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def has_area(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Bounding box must have positive area")
        return self


class DetectionResponse(BaseModel):
    id: str
    predicted_class: int
    model_class_id: int | None = None
    qcvn_code: str
    name_vi: str
    confidence: float
    is_uncertain: bool
    bbox: BoundingBox | None


class RunResponse(BaseModel):
    id: str
    image_id: str
    engine: Literal["cnn", "yolo"]
    task: Literal["classification", "detection"]
    model_version: str
    mapping_sha256: str | None = None
    catalog_sha256: str | None = None
    created_at: datetime
    detections: list[DetectionResponse]


class ObservationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detection_id: str = Field(min_length=1, max_length=36)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    location_source: Literal["manual_pin", "device", "exif", "user_confirmed"] = "user_confirmed"
    proposed_class: int | None = Field(default=None, ge=0, strict=True)
    correction_reason: str | None = Field(default=None, max_length=1000)


class ObservationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: str = Field(min_length=1, max_length=36)
    items: list[ObservationItem] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def distinct_detections(self):
        if len({item.detection_id for item in self.items}) != len(self.items):
            raise ValueError("Each detection can only appear once")
        return self


class ObservationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["accept", "reject"]
    comment: str | None = Field(default=None, max_length=1000)


class ObservationResponse(BaseModel):
    id: str
    image_id: str
    detection: DetectionResponse
    engine: Literal["cnn", "yolo"]
    model_version: str
    created_by: str
    latitude: float
    longitude: float
    location_source: str
    proposed_class: int | None
    proposed_qcvn_code: str | None = None
    proposed_name_vi: str | None = None
    correction_reason: str | None
    status: Literal["pending", "accepted", "rejected"]
    created_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_comment: str | None
    sign_record_id: str | None


class ObservationPage(BaseModel):
    items: list[ObservationResponse]
    total: int
    offset: int
    limit: int
