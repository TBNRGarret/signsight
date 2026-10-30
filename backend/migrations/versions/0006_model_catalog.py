"""Retain model-output indices and mapping/catalog fingerprints without renumbering records."""
from alembic import op
import sqlalchemy as sa

revision='0006_model_catalog'
down_revision='0005_duplicate_links'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE inference_runs ADD COLUMN mapping_sha256 VARCHAR(64)')
    op.execute('ALTER TABLE inference_runs ADD COLUMN catalog_sha256 VARCHAR(64)')
    op.execute('ALTER TABLE image_detections ADD COLUMN model_class_id INTEGER')
    op.create_table('sign_catalog_entries',sa.Column('id',sa.Integer,primary_key=True,autoincrement=False),
                    sa.Column('qcvn_code',sa.String(20),unique=True,nullable=False),
                    sa.Column('name_vi',sa.String(255),nullable=False))


def downgrade():
    raise RuntimeError('Restore a backup instead of dropping inference provenance')
