"""Add durable account-scoped receipts without modifying existing resources."""
from alembic import op
import sqlalchemy as sa

revision = "0007_write_receipts"
down_revision = "0006_model_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("write_receipts",
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("operation", sa.String(30), primary_key=True),
        sa.Column("request_key", sa.String(128), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result_ids", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False))


def downgrade():
    raise RuntimeError("Restore a backup instead of discarding write recovery receipts")
