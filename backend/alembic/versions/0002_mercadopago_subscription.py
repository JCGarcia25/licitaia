"""Campos de suscripción para Mercado Pago."""
from alembic import op
import sqlalchemy as sa

revision = "0002_mercadopago_subscription"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("subscriptions")}
    if "external_id" not in columns:
        op.add_column("subscriptions", sa.Column("external_id", sa.String(length=120), nullable=True))
    if "checkout_url" not in columns:
        op.add_column("subscriptions", sa.Column("checkout_url", sa.String(length=1000), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("subscriptions")}
    if "ix_subscriptions_external_id" not in indexes:
        op.create_index("ix_subscriptions_external_id", "subscriptions", ["external_id"], unique=False)

def downgrade():
    op.drop_index("ix_subscriptions_external_id", table_name="subscriptions")
    op.drop_column("subscriptions", "checkout_url")
    op.drop_column("subscriptions", "external_id")
