"""Versiones de matching, trabajos recuperables e historial no destructivo."""
from alembic import op
import sqlalchemy as sa

revision = '0011_match_jobs'
down_revision = '0010_sync_cursor'
branch_labels = None
depends_on = None

COLUMNS = {
    'company_profiles': [('match_version', sa.String(64))],
    'opportunities': [('match_version', sa.String(64))],
    'opportunity_embeddings': [('content_version', sa.String(64))],
    'user_opportunities': [('match_state', sa.String(16)), ('profile_version', sa.String(64)),
        ('opportunity_version', sa.String(64)), ('algorithm_version', sa.String(64)),
        ('embedding_version', sa.String(64)), ('scored_at', sa.DateTime()), ('match_error', sa.String(80))],
}


def upgrade():
    # 0001 usa modelos actuales: soportar tanto objetos ya creados como ausentes.
    for table, fields in COLUMNS.items():
        existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for name, kind in fields:
            if name not in existing:
                op.add_column(table, sa.Column(name, kind, nullable=True))
    op.create_table('match_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('active_key', sa.Integer(), unique=True, nullable=True),
        sa.Column('state', sa.String(24), nullable=False),
        sa.Column('profile_version', sa.String(64)),
        sa.Column('algorithm_version', sa.String(64), nullable=False),
        sa.Column('embedding_version', sa.String(64), nullable=False),
        *[sa.Column(c, sa.Integer(), nullable=False) for c in ('cursor_id','max_id','candidate_total','excluded_total','examined','scored','skipped','failed','batches','retries')],
        sa.Column('lease_token', sa.String(36)), sa.Column('lease_until', sa.DateTime()),
        sa.Column('error', sa.String(80)), sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False), sa.Column('finished_at', sa.DateTime()),
        sa.Column('last_batch_seconds', sa.Float()),
        sa.Column('profile_vector', sa.JSON()),
        sa.Column('processing_seconds', sa.Float(), nullable=False),
        sa.Column('last_batch_queries', sa.Integer()), sa.Column('peak_rss_bytes', sa.Float()),
        if_not_exists=True)
    if 'ix_match_jobs_user_id' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('match_jobs')}:
        op.create_index('ix_match_jobs_user_id', 'match_jobs', ['user_id'])
    op.create_table('match_slots', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token', sa.String(36)), sa.Column('lease_until', sa.DateTime()), if_not_exists=True)
    op.create_table('match_score_history', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), sa.ForeignKey('opportunities.id'), nullable=False),
        sa.Column('score', sa.Float()), sa.Column('reasons', sa.JSON()), sa.Column('versions', sa.JSON()),
        sa.Column('recorded_at', sa.DateTime(), nullable=False), if_not_exists=True)


def downgrade():
    bind = op.get_bind()
    # No descartar historial ni interrumpir trabajos al revertir un esquema.
    if bind.execute(sa.text('SELECT count(*) FROM match_score_history')).scalar():
        raise RuntimeError('Rollback requiere conservar/exportar el historial de matching antes de retirar 0011')
    if bind.execute(sa.text('SELECT count(*) FROM match_jobs WHERE active_key IS NOT NULL')).scalar():
        raise RuntimeError('Detener y cancelar trabajos de matching antes de retirar 0011')
    for table in ('match_score_history', 'match_slots', 'match_jobs'):
        op.drop_table(table)
    for table, fields in reversed(list(COLUMNS.items())):
        for name, _ in reversed(fields):
            op.drop_column(table, name)
