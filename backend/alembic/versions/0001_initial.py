"""Migración inicial de LicitaIA.

Decisión (ADR-007): la primera migración delega en Base.metadata.create_all para
garantizar paridad exacta con los modelos de app/db/models.py (columna única de
verdad). Migraciones posteriores sí se escriben a mano con op.add_column, etc.

Revision ID: 0001
Revises:
Create Date: 2026-10-27
"""
from alembic import op

from app.db.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
