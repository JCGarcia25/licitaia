"""Guarda la última búsqueda de oportunidades por usuario."""
from alembic import op
import sqlalchemy as sa

revision = "0008_last_opportunity_search"
down_revision = "0007_alert_email_to"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("last_opportunity_search", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("users", "last_opportunity_search")
