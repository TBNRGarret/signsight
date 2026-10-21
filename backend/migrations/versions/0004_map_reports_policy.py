"""Audited policy, sign revisions and moderated evidence-backed change reports."""
from alembic import op
import sqlalchemy as sa

revision="0004_map_reports_policy"
down_revision="0003_images_observations"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('sign_records',sa.Column('revision',sa.Integer,nullable=False,server_default='0'))
    op.create_index('ix_sign_records_location','sign_records',['latitude','longitude'])
    op.create_table('app_policy',sa.Column('id',sa.Integer,primary_key=True),sa.Column('confirmation_days',sa.Integer,nullable=False),
        sa.Column('revision',sa.Integer,nullable=False),sa.Column('updated_by',sa.String(36),sa.ForeignKey('users.id')),
        sa.Column('updated_at',sa.DateTime,nullable=False))
    op.create_table('policy_audit',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('before_days',sa.Integer,nullable=False),sa.Column('after_days',sa.Integer,nullable=False),
        sa.Column('revision',sa.Integer,nullable=False),sa.Column('created_at',sa.DateTime,nullable=False))
    op.create_table('sign_reports',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('record_id',sa.String(36),sa.ForeignKey('sign_records.id'),nullable=False),
        sa.Column('image_id',sa.String(36),sa.ForeignKey('uploaded_images.id'),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(30),nullable=False),sa.Column('comment',sa.Text,nullable=False),
        sa.Column('base_revision',sa.Integer,nullable=False),sa.Column('proposed_class',sa.Integer),
        sa.Column('latitude',sa.Float),sa.Column('longitude',sa.Float),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('created_at',sa.DateTime,nullable=False),sa.Column('reviewed_by',sa.String(36),sa.ForeignKey('users.id')),
        sa.Column('reviewed_at',sa.DateTime),sa.Column('review_comment',sa.Text))
    for field in ('record_id','created_by','status'): op.create_index('ix_sign_reports_'+field,'sign_reports',[field])
    op.create_table('sign_audit',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('record_id',sa.String(36),sa.ForeignKey('sign_records.id'),nullable=False),
        sa.Column('report_id',sa.String(36),sa.ForeignKey('sign_reports.id')),
        sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(30),nullable=False),
        sa.Column('before_json',sa.Text,nullable=False),sa.Column('after_json',sa.Text,nullable=False),sa.Column('created_at',sa.DateTime,nullable=False))
    op.create_index('ix_sign_audit_record_id','sign_audit',['record_id'])


def downgrade(): raise RuntimeError('Restore a backup instead of discarding report history')
