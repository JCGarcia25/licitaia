"""Campos para recuperación segura de contraseña."""
from alembic import op
import sqlalchemy as sa

revision = "0003_password_reset"
down_revision = "0002_mercadopago_subscription"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "password_reset_token" not in columns:
        op.add_column("users", sa.Column("password_reset_token", sa.String(length=64), nullable=True))
    if "password_reset_expires_at" not in columns:
        op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))
    if "ix_users_password_reset_token" not in {i["name"] for i in inspector.get_indexes("users")}:
        op.create_index("ix_users_password_reset_token", "users", ["password_reset_token"], unique=False)

def downgrade():
    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token")
