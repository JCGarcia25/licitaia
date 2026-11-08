"""Aísla la auditoría de sincronizaciones por usuario."""
from alembic import op
import sqlalchemy as sa
revision = "0005_sync_run_user"
down_revision = "0004_sync_usage"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("sync_runs", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_sync_runs_user_id", "sync_runs", ["user_id"])
def downgrade():
    op.drop_index("ix_sync_runs_user_id", table_name="sync_runs")
    op.drop_column("sync_runs", "user_id")
