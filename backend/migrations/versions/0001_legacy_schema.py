"""Create or adopt the original five-table schema without replacing existing rows."""

from alembic import op
import sqlalchemy as sa

revision = "0001_legacy_schema"
down_revision = None
branch_labels = None
depends_on = None


def legacy_metadata():
    metadata = sa.MetaData()
    sa.Table("users", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(50), server_default="contributor"),
        sa.Column("reputation_score", sa.Integer, server_default="100"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    signs = sa.Table("sign_records", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("predicted_class", sa.Integer, nullable=False),
        sa.Column("qcvn_code", sa.String(20), nullable=False),
        sa.Column("name_vi", sa.String(255), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("is_uncertain", sa.Boolean, server_default=sa.false()),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("location_source", sa.String(50), server_default="user_confirmed"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column("last_confirmed_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
    )
    evidence = sa.Table("evidence", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("sign_records.id", ondelete="CASCADE")),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("image_hash", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    sa.Table("confirmation_events", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("sign_records.id", ondelete="CASCADE")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("evidence_id", sa.String(36), sa.ForeignKey("evidence.id")),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    sa.Table("duplicate_candidates", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("new_record_id", sa.String(36), sa.ForeignKey("sign_records.id", ondelete="CASCADE")),
        sa.Column("existing_record_id", sa.String(36), sa.ForeignKey("sign_records.id", ondelete="CASCADE")),
        sa.Column("distance_meters", sa.Float, nullable=False),
        sa.Column("class_match", sa.Boolean, nullable=False),
        sa.Column("similarity_score", sa.Float, server_default="0"),
        sa.Column("status", sa.String(50), server_default="pending_review"),
    )
    sa.Index("idx_signs_location", signs.c.latitude, signs.c.longitude)
    sa.Index("idx_signs_status", signs.c.status)
    sa.Index("idx_signs_expires_at", signs.c.expires_at)
    sa.Index("idx_evidence_record", evidence.c.record_id)
    sa.Index("idx_evidence_hash", evidence.c.image_hash)
    return metadata


def upgrade():
    connection = op.get_bind()
    metadata = legacy_metadata()
    inspector = sa.inspect(connection)
    existing = set(inspector.get_table_names())
    for table in metadata.tables.values():
        if table.name in existing:
            columns = {column["name"] for column in inspector.get_columns(table.name)}
            missing = set(table.columns.keys()) - columns
            if missing:
                raise RuntimeError(f"Unexpected legacy schema for {table.name}; missing {sorted(missing)}")
    metadata.create_all(connection, checkfirst=True)
    for table in metadata.tables.values():
        for index in table.indexes:
            index.create(connection, checkfirst=True)


def downgrade():
    raise RuntimeError("Downgrade would remove legacy records; restore a database backup instead")
