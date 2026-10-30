import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, false
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class SignCatalogEntry(Base):
    __tablename__ = 'sign_catalog_entries'

    id = Column(Integer,primary_key=True,autoincrement=False)
    qcvn_code = Column(String(20),unique=True,nullable=False)
    name_vi = Column(String(255),nullable=False)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), default="user", nullable=False)
    password_hash = Column(String(255), nullable=True)  # Legacy accounts have no password.
    is_active = Column(Boolean, nullable=False, default=True, server_default=false())
    credential_version = Column(Integer, nullable=False, default=0, server_default="0")
    reputation_score = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("SignRecord", back_populates="creator")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    credential_version = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)


class AccountAudit(Base):
    __tablename__ = "account_audit"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    target_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SignRecord(Base):
    __tablename__ = "sign_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    predicted_class = Column(Integer, nullable=False)
    qcvn_code = Column(String(20), nullable=False)
    name_vi = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=False)
    is_uncertain = Column(Boolean, default=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_source = Column(String(50), default="user_confirmed")
    status = Column(String(50), default="active")  # 'active', 'pending_revalidation', 'expired', 'removed'
    verification_status = Column(String(30), nullable=False, default="unverified", server_default="unverified")
    confirmation_days = Column(Integer, nullable=True)  # NULL preserves the legacy per-class policy.
    revision = Column(Integer, nullable=False, default=0, server_default="0")
    merged_into_id = Column(String(36), ForeignKey('sign_records.id'), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_confirmed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    creator = relationship("User", back_populates="records")
    evidences = relationship("Evidence", back_populates="sign_record", cascade="all, delete-orphan")
    confirmations = relationship("ConfirmationEvent", back_populates="sign_record", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(36), ForeignKey("sign_records.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(500), nullable=False)
    image_hash = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sign_record = relationship("SignRecord", back_populates="evidences")


class ConfirmationEvent(Base):
    __tablename__ = "confirmation_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(36), ForeignKey("sign_records.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)  # 'confirm_existing', 'report_removed', 'report_damaged', 'update_evidence'
    comment = Column(Text, nullable=True)
    evidence_id = Column(String(36), ForeignKey("evidence.id"), nullable=True)
    confirmed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    sign_record = relationship("SignRecord", back_populates="confirmations")


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    new_record_id = Column(String(36), ForeignKey("sign_records.id", ondelete="CASCADE"), nullable=False)
    existing_record_id = Column(String(36), ForeignKey("sign_records.id", ondelete="CASCADE"), nullable=False)
    distance_meters = Column(Float, nullable=False)
    class_match = Column(Boolean, nullable=False)
    similarity_score = Column(Float, default=0.0)
    status = Column(String(50), default="pending_review")  # 'pending_review', 'confirmed_duplicate', 'dismissed'


class UploadedImage(Base):
    __tablename__ = "uploaded_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    storage_key = Column(String(50), nullable=False, unique=True)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    exif_latitude = Column(Float, nullable=True)
    exif_longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InferenceRun(Base):
    __tablename__ = "inference_runs"
    mapping_sha256 = Column(String(64), nullable=True)
    catalog_sha256 = Column(String(64), nullable=True)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String(36), ForeignKey("uploaded_images.id"), nullable=False, index=True)
    engine = Column(String(20), nullable=False)
    model_version = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    detections = relationship("ImageDetection", order_by="ImageDetection.ordinal")


class ImageDetection(Base):
    __tablename__ = "image_detections"
    model_class_id = Column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("run_id", "ordinal", name="uq_detection_run_ordinal"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("inference_runs.id"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    predicted_class = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    x1 = Column(Float, nullable=True)
    y1 = Column(Float, nullable=True)
    x2 = Column(Float, nullable=True)
    y2 = Column(Float, nullable=True)
    run = relationship("InferenceRun", overlaps="detections")


class Observation(Base):
    __tablename__ = "observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detection_id = Column(String(36), ForeignKey("image_detections.id"), nullable=False, unique=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_source = Column(String(30), nullable=False)
    proposed_class = Column(Integer, nullable=True)
    correction_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)
    sign_record_id = Column(String(36), ForeignKey("sign_records.id"), nullable=True, unique=True)
    detection = relationship("ImageDetection")


class AppPolicy(Base):
    __tablename__ = "app_policy"
    id = Column(Integer, primary_key=True)
    confirmation_days = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False, default=0)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PolicyAudit(Base):
    __tablename__ = "policy_audit"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    before_days = Column(Integer, nullable=False)
    after_days = Column(Integer, nullable=False)
    revision = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SignReport(Base):
    __tablename__ = "sign_reports"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(36), ForeignKey("sign_records.id"), nullable=False, index=True)
    image_id = Column(String(36), ForeignKey("uploaded_images.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(30), nullable=False)
    comment = Column(Text, nullable=False)
    base_revision = Column(Integer, nullable=False)
    proposed_class = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)


class SignAudit(Base):
    __tablename__ = "sign_audit"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(36), ForeignKey("sign_records.id"), nullable=False, index=True)
    report_id = Column(String(36), ForeignKey("sign_reports.id"), nullable=True)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(30), nullable=False)
    before_json = Column(Text, nullable=False)
    after_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
