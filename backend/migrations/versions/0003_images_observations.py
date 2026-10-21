"""Persist sanitized image evidence, immutable inference and reviewed observations."""

from alembic import op
import sqlalchemy as sa

revision = "0003_images_observations"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sign_records", sa.Column("verification_status", sa.String(30), nullable=False, server_default="unverified"))
    op.add_column("sign_records", sa.Column("confirmation_days", sa.Integer, nullable=True))
    op.execute("UPDATE sign_records SET verification_status = 'needs_confirmation' WHERE status IN ('expired', 'pending_revalidation')")
    op.create_table("uploaded_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("storage_key", sa.String(50), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("exif_latitude", sa.Float), sa.Column("exif_longitude", sa.Float),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_uploaded_images_uploaded_by", "uploaded_images", ["uploaded_by"])
    op.create_table("inference_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("image_id", sa.String(36), sa.ForeignKey("uploaded_images.id"), nullable=False),
        sa.Column("engine", sa.String(20), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_inference_runs_image_id", "inference_runs", ["image_id"])
    op.create_table("image_detections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("inference_runs.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("predicted_class", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("x1", sa.Float), sa.Column("y1", sa.Float), sa.Column("x2", sa.Float), sa.Column("y2", sa.Float),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_detection_run_ordinal"),
    )
    op.create_index("ix_image_detections_run_id", "image_detections", ["run_id"])
    op.create_table("observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("detection_id", sa.String(36), sa.ForeignKey("image_detections.id"), nullable=False, unique=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("latitude", sa.Float, nullable=False), sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("location_source", sa.String(30), nullable=False),
        sa.Column("proposed_class", sa.Integer), sa.Column("correction_reason", sa.Text),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime), sa.Column("review_comment", sa.Text),
        sa.Column("sign_record_id", sa.String(36), sa.ForeignKey("sign_records.id"), unique=True),
    )
    op.create_index("ix_observations_created_by", "observations", ["created_by"])
    op.create_index("ix_observations_status", "observations", ["status"])


def downgrade():
    raise RuntimeError("Downgrade would discard image and observation provenance; restore a backup instead")
