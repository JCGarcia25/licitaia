"""Separar entradas del intento fallido de las del último score conservado."""
from alembic import op
import sqlalchemy as sa
revision='0012_failed_match_inputs'
down_revision='0011_match_jobs'
branch_labels=None
depends_on=None


def upgrade():
    columns={c['name'] for c in sa.inspect(op.get_bind()).get_columns('user_opportunities')}
    if 'failed_input_versions' not in columns:
        op.add_column('user_opportunities',sa.Column('failed_input_versions',sa.JSON(none_as_null=True),nullable=True))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM user_opportunities WHERE failed_input_versions IS NOT NULL')).scalar():
        raise RuntimeError('Conservar metadata de intentos fallidos antes de retirar 0012')
    op.drop_column('user_opportunities','failed_input_versions')
