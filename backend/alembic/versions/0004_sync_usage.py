"""Contador mensual de sincronizaciones gratuitas."""
from alembic import op
import sqlalchemy as sa
revision = "0004_sync_usage"
down_revision = "0003_password_reset"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("sync_usage", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("month", sa.String(7), nullable=False), sa.Column("successful_runs", sa.Integer(), nullable=False, server_default="0"), sa.UniqueConstraint("user_id", "month", name="uq_sync_usage_user_month"))
    op.create_index("ix_sync_usage_user_id", "sync_usage", ["user_id"])
    op.create_index("ix_sync_usage_month", "sync_usage", ["month"])
def downgrade():
    op.drop_table("sync_usage")
