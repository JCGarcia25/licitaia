"""Progreso incremental de sincronización por fuente."""
from alembic import op
import sqlalchemy as sa

revision = "0010_sync_cursor"
down_revision = "0009_landing_visits"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("sync_cursors"):
        return
    op.create_table(
        "sync_cursors", sa.Column("source", sa.String(60), primary_key=True),
        sa.Column("dataset_id", sa.String(40), nullable=False),
        sa.Column("cursor_time", sa.DateTime()), sa.Column("cursor_id", sa.String(255)),
        sa.Column("high_watermark", sa.DateTime()),
        sa.Column("mode", sa.String(24), nullable=False, server_default="incremental"),
        sa.Column("status", sa.String(24), nullable=False, server_default="idle"),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime()),
    )


def downgrade():
    op.drop_table("sync_cursors")
