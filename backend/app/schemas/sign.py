from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field

class ProbabilityItem(BaseModel):
    class_id: int
    qcvn_code: str
    name_vi: str
    probability: float

class InferenceResponse(BaseModel):
    predicted_class: int
    qcvn_code: str
    name_vi: str
    name_en: str
    confidence: float
    is_uncertain: bool
    probabilities: List[ProbabilityItem] = Field(default_factory=list)

class SignRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predicted_class: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_source: Literal["exif", "device", "manual", "manual_pin", "user_confirmed"] = "user_confirmed"

class SignRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    predicted_class: int
    qcvn_code: str
    name_vi: str
    confidence: float
    is_uncertain: bool
    latitude: float
    longitude: float
    location_source: str
    status: str
    verification_status: str = "unverified"
    confirmation_days: Optional[int] = None
    revision: int = 0
    merged_into_id: Optional[str] = None
    created_at: datetime
    last_confirmed_at: datetime
    expires_at: datetime
    created_by: Optional[str] = None
    possible_duplicate_count: Optional[int] = 0


class RevalidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["confirm_existing", "report_removed", "report_damaged"]
    comment: Optional[str] = Field(default=None, max_length=2000)
