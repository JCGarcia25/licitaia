"""Add private experimental V2 tables; preserve all historical scores."""
from alembic import op
import sqlalchemy as sa
revision = '0013_compatibility_shadow'
down_revision = '0012_failed_match_inputs'
branch_labels = None
depends_on = None


def upgrade():
    # Explicit definitions keep this revision independent of future ORM changes.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'compatibility_evidence_profiles' not in existing:
        op.create_table('compatibility_evidence_profiles',sa.Column('id',sa.Integer,primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('payload',sa.JSON,nullable=False),sa.Column('version',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime,nullable=False))
        op.create_index('ix_compatibility_evidence_profiles_user_id','compatibility_evidence_profiles',['user_id'])
    if 'compatibility_shadow_runs' not in existing:
        op.create_table('compatibility_shadow_runs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('state',sa.String(24),nullable=False),sa.Column('snapshot',sa.JSON,nullable=False),sa.Column('model_version',sa.String(64),nullable=False),sa.Column('cursor',sa.Integer,nullable=False),sa.Column('lease_token',sa.String(36)),sa.Column('lease_until',sa.DateTime),sa.Column('created_at',sa.DateTime,nullable=False),sa.Column('finished_at',sa.DateTime),sa.Column('error',sa.String(120)))
        op.create_index('ix_compatibility_shadow_runs_user_id','compatibility_shadow_runs',['user_id'])
    if 'compatibility_shadow_results' not in existing:
        op.create_table('compatibility_shadow_results',sa.Column('id',sa.Integer,primary_key=True),sa.Column('run_id',sa.String(36),sa.ForeignKey('compatibility_shadow_runs.id'),nullable=False),sa.Column('opportunity_id',sa.Integer,sa.ForeignKey('opportunities.id'),nullable=False),sa.Column('legacy_score',sa.Float),sa.Column('legacy_versions',sa.JSON,nullable=False),sa.Column('result',sa.JSON,nullable=False),sa.Column('duration_ms',sa.Float,nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),sa.UniqueConstraint('run_id','opportunity_id',name='uq_compatibility_shadow_result'))
        op.create_index('ix_compatibility_shadow_results_run_id','compatibility_shadow_results',['run_id'])


def downgrade():
    tables = ('compatibility_shadow_results','compatibility_shadow_runs','compatibility_evidence_profiles')
    for table in tables:
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():
            raise RuntimeError('Conservar evidencia e historial V2 antes de retirar 0013; rollback operativo: desactivar flag')
    for table in tables:
        op.drop_table(table)
