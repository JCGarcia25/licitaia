"""Aísla la auditoría de sincronizaciones por usuario."""
from alembic import op
import sqlalchemy as sa
revision = "0005_sync_run_user"
down_revision = "0004_sync_usage"
branch_labels = None
depends_on = None
def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "user_id" not in {c["name"] for c in inspector.get_columns("sync_runs")}:
        with op.batch_alter_table("sync_runs") as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_sync_runs_user_id_users", "users", ["user_id"], ["id"])
    if "ix_sync_runs_user_id" not in {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("sync_runs")}:
        op.create_index("ix_sync_runs_user_id", "sync_runs", ["user_id"])
def downgrade():
    op.drop_index("ix_sync_runs_user_id", table_name="sync_runs")
    op.drop_column("sync_runs", "user_id")
