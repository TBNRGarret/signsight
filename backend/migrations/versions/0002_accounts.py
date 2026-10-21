"""Add password hashes, revocable sessions and account administration audit."""

from alembic import op
import sqlalchemy as sa

revision = "0002_accounts"
down_revision = "0001_legacy_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    # Old users never receive a default password or an enabled account.
    op.add_column("users", sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("credential_version", sa.Integer, nullable=False, server_default="0"))
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR role NOT IN ('user', 'manager', 'admin')")
    users = sa.table("users", sa.column("username"), sa.column("email"))
    op.create_index("uq_users_username_lower", "users", [sa.func.lower(users.c.username)], unique=True)
    op.create_index("uq_users_email_lower", "users", [sa.func.lower(users.c.email)], unique=True)
    op.create_table("auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("credential_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table("account_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade():
    raise RuntimeError("Account downgrade would discard credentials/audit; restore a backup instead")
