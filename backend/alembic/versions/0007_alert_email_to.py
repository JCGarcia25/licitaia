"""Permite elegir el destinatario de los resúmenes de alertas."""
from alembic import op
import sqlalchemy as sa

revision = "0007_alert_email_to"
down_revision = "0006_admin_presence"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("alert_prefs", sa.Column("email_to", sa.String(length=255), nullable=True))

def downgrade():
    op.drop_column("alert_prefs", "email_to")
