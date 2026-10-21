"""Preserve merged observations as links, keeping original rows and evidence."""
from alembic import op
revision='0005_duplicate_links'
down_revision='0004_map_reports_policy'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('ALTER TABLE sign_records ADD COLUMN merged_into_id VARCHAR(36) REFERENCES sign_records(id)')
    op.create_index('ix_sign_records_merged_into_id','sign_records',['merged_into_id'])


def downgrade(): raise RuntimeError('Restore a backup instead of discarding merge provenance')
