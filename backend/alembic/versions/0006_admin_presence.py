"""Presencia de usuarios para el panel privado de administración."""
from alembic import op
import sqlalchemy as sa

revision = "0006_admin_presence"
down_revision = "0005_sync_run_user"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("current_path", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_user_agent", sa.String(length=255), nullable=True))
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])

def downgrade():
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_column("users", "last_user_agent")
    op.drop_column("users", "current_path")
    op.drop_column("users", "last_seen_at")
