"""Campos de suscripción para Mercado Pago."""
from alembic import op
import sqlalchemy as sa

revision = "0002_mercadopago_subscription"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("subscriptions", sa.Column("external_id", sa.String(length=120), nullable=True))
    op.add_column("subscriptions", sa.Column("checkout_url", sa.String(length=1000), nullable=True))
    op.create_index("ix_subscriptions_external_id", "subscriptions", ["external_id"], unique=False)

def downgrade():
    op.drop_index("ix_subscriptions_external_id", table_name="subscriptions")
    op.drop_column("subscriptions", "checkout_url")
    op.drop_column("subscriptions", "external_id")
