"""Private DEV-only evaluation entities; no changes to commercial tables."""
from alembic import op
import sqlalchemy as sa
revision='0014_evaluation_platform'
down_revision='0013_compatibility_shadow'
branch_labels=None
depends_on=None

def upgrade():
    existing=set(sa.inspect(op.get_bind()).get_table_names())
    if 'evaluation_environment_identities' not in existing:
        op.create_table('evaluation_environment_identities',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('fingerprint',sa.String(length=64),nullable=False,unique=True),
            sa.Column('purpose',sa.String(length=32),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
        )
    if 'evaluation_campaigns' not in existing:
        op.create_table('evaluation_campaigns',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('owner_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
            sa.Column('name',sa.String(length=160),nullable=False),
            sa.Column('state',sa.String(length=24),nullable=False),
            sa.Column('data_scope',sa.String(length=24),nullable=False),
            sa.Column('config',sa.JSON(),nullable=False),
            sa.Column('universe',sa.JSON(),nullable=False),
            sa.Column('selection',sa.JSON(),nullable=True),
            sa.Column('cursor',sa.Integer(),nullable=False),
            sa.Column('lease_token',sa.String(length=36),nullable=True),
            sa.Column('lease_until',sa.DateTime(),nullable=True),
            sa.Column('semantic_disabled_at',sa.DateTime(),nullable=True),
            sa.Column('external_calls',sa.Integer(),nullable=False),
            sa.Column('reserved_cost',sa.Float(),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
            sa.Column('expires_at',sa.DateTime(),nullable=False),
            sa.Column('closed_at',sa.DateTime(),nullable=True),
        )
        op.create_index('ix_evaluation_campaigns_owner_user_id','evaluation_campaigns',['owner_user_id'])
    if 'evaluation_samples' not in existing:
        op.create_table('evaluation_samples',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('campaign_id',sa.String(length=36),sa.ForeignKey('evaluation_campaigns.id'),nullable=False),
            sa.Column('pair_key',sa.String(length=64),nullable=False),
            sa.Column('process_key',sa.String(length=255),nullable=False),
            sa.Column('snapshot',sa.JSON(),nullable=False),
            sa.Column('stratum',sa.JSON(),nullable=False),
            sa.Column('inclusion_probability',sa.Float(),nullable=False),
            sa.Column('split',sa.String(length=20),nullable=False),
            sa.UniqueConstraint('campaign_id','pair_key',name='uq_evaluation_sample_pair'),
        )
        op.create_index('ix_evaluation_samples_campaign_id','evaluation_samples',['campaign_id'])
    if 'evaluation_assignments' not in existing:
        op.create_table('evaluation_assignments',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('sample_id',sa.String(length=36),sa.ForeignKey('evaluation_samples.id'),nullable=False),
            sa.Column('evaluator_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
            sa.Column('kind',sa.String(length=20),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
            sa.UniqueConstraint('sample_id','evaluator_user_id',name='uq_evaluation_assignment'),
        )
        op.create_index('ix_evaluation_assignments_evaluator_user_id','evaluation_assignments',['evaluator_user_id'])
        op.create_index('ix_evaluation_assignments_sample_id','evaluation_assignments',['sample_id'])
    if 'evaluation_judgments' not in existing:
        op.create_table('evaluation_judgments',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('assignment_id',sa.String(length=36),sa.ForeignKey('evaluation_assignments.id'),nullable=False,unique=True),
            sa.Column('payload',sa.JSON(),nullable=False),
            sa.Column('criteria_version',sa.String(length=64),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
        )
    if 'evaluation_adjudications' not in existing:
        op.create_table('evaluation_adjudications',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('sample_id',sa.String(length=36),sa.ForeignKey('evaluation_samples.id'),nullable=False,unique=True),
            sa.Column('assignment_id',sa.String(length=36),sa.ForeignKey('evaluation_assignments.id'),nullable=False,unique=True),
            sa.Column('payload',sa.JSON(),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
        )
    if 'evaluation_reports' not in existing:
        op.create_table('evaluation_reports',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('campaign_id',sa.String(length=36),sa.ForeignKey('evaluation_campaigns.id'),nullable=False,unique=True),
            sa.Column('payload',sa.JSON(),nullable=False),
            sa.Column('version',sa.String(length=64),nullable=False),
            sa.Column('created_at',sa.DateTime(),nullable=False),
        )
    if 'evaluation_embeddings' not in existing:
        op.create_table('evaluation_embeddings',
            sa.Column('id',sa.String(length=36),nullable=False,primary_key=True),
            sa.Column('owner_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
            sa.Column('campaign_id',sa.String(length=36),sa.ForeignKey('evaluation_campaigns.id'),nullable=False),
            sa.Column('cache_key',sa.String(length=64),nullable=False),
            sa.Column('text_hash',sa.String(length=64),nullable=False),
            sa.Column('model',sa.String(length=80),nullable=False),
            sa.Column('dimensions',sa.Integer(),nullable=False),
            sa.Column('version',sa.String(length=64),nullable=False),
            sa.Column('state',sa.String(length=24),nullable=False),
            sa.Column('vector',sa.JSON(),nullable=True),
            sa.Column('usage_tokens',sa.Integer(),nullable=True),
            sa.Column('estimated_cost',sa.Float(),nullable=True),
            sa.Column('created_at',sa.DateTime(),nullable=False),
            sa.Column('expires_at',sa.DateTime(),nullable=False),
            sa.UniqueConstraint('owner_user_id','cache_key',name='uq_evaluation_embedding_private'),
        )
        op.create_index('ix_evaluation_embeddings_campaign_id','evaluation_embeddings',['campaign_id'])
    if 'evaluation_exposures' not in existing:
        op.create_table('evaluation_exposures',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('pair_key',sa.String(64),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('user_id','pair_key',name='uq_evaluation_exposure'))
    if 'evaluation_data_grants' not in existing:
        op.create_table('evaluation_data_grants',sa.Column('id',sa.String(36),primary_key=True),sa.Column('owner_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('administrator_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('run_id',sa.String(36),sa.ForeignKey('compatibility_shadow_runs.id'),nullable=False),sa.Column('state',sa.String(16),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False))
        op.create_index('ix_evaluation_data_grants_owner_user_id','evaluation_data_grants',['owner_user_id'])

def downgrade():
    tables=('evaluation_data_grants', 'evaluation_exposures', 'evaluation_embeddings', 'evaluation_reports', 'evaluation_adjudications', 'evaluation_judgments', 'evaluation_assignments', 'evaluation_samples', 'evaluation_campaigns', 'evaluation_environment_identities')
    for table in tables:
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():
            raise RuntimeError('Conservar historial de evaluación; rollback operativo: desactivar evaluación')
    for table in tables:op.drop_table(table)
