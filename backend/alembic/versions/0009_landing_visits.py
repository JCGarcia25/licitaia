"""Registra sesiones anónimas del landing."""
from alembic import op
import sqlalchemy as sa

revision = "0009_landing_visits"
down_revision = "0008_last_opportunity_search"
branch_labels = None
depends_on = None

def upgrade():
    if sa.inspect(op.get_bind()).has_table("landing_visits"):
        return
    op.create_table("landing_visits", sa.Column("id", sa.String(36), primary_key=True), sa.Column("started_at", sa.DateTime(), nullable=False), sa.Column("last_seen_at", sa.DateTime(), nullable=False), sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"), sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_landing_visits_started_at", "landing_visits", ["started_at"])
    op.create_index("ix_landing_visits_last_seen_at", "landing_visits", ["last_seen_at"])

def downgrade():
    op.drop_table("landing_visits")
