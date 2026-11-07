"""Campos para recuperación segura de contraseña."""
from alembic import op
import sqlalchemy as sa

revision = "0003_password_reset"
down_revision = "0002_mercadopago_subscription"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("password_reset_token", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_password_reset_token", "users", ["password_reset_token"], unique=False)

def downgrade():
    op.drop_index("ix_users_password_reset_token", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token")
