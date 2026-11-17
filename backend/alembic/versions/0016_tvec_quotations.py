"""Public quotation snapshots, separate from purchase orders and SECOP scoring."""
from alembic import op
import sqlalchemy as sa

revision = '0016_tvec_quotations'
down_revision = '0015_tvec_orders'
branch_labels = None
depends_on = None


def upgrade():
    ins = sa.inspect(op.get_bind())
    if not ins.has_table('tvec_quotation_events'):
        op.create_table('tvec_quotation_events',
            sa.Column('official_id', sa.String(32), primary_key=True),
            sa.Column('title', sa.Text(), nullable=False),
            sa.Column('buyer', sa.Text(), nullable=False),
            sa.Column('instrument', sa.Text(), nullable=False),
            sa.Column('status', sa.String(80), nullable=False),
            sa.Column('kind', sa.String(12), nullable=False),
            sa.Column('kind_evidence', sa.String(64), nullable=False),
            sa.Column('opens_at', sa.DateTime(), nullable=False),
            sa.Column('closes_at', sa.DateTime(), nullable=False),
            sa.Column('official_url', sa.Text(), nullable=False),
            sa.Column('detail_verified', sa.Boolean(), nullable=False),
            sa.Column('checked_at', sa.DateTime(), nullable=False),
            sa.Column('snapshot_id', sa.String(36), nullable=False))
    if not ins.has_table('tvec_quotation_snapshots'):
        op.create_table('tvec_quotation_snapshots',
            sa.Column('source', sa.String(32), primary_key=True),
            sa.Column('published_snapshot', sa.String(36)),
            sa.Column('checked_at', sa.DateTime()),
            sa.Column('status', sa.String(16), nullable=False),
            sa.Column('lease_token', sa.String(36)),
            sa.Column('lease_until', sa.DateTime()),
            sa.Column('scanned_pages', sa.Integer(), nullable=False),
            sa.Column('scanned_rows', sa.Integer(), nullable=False),
            sa.Column('excluded_rfi', sa.Integer(), nullable=False),
            sa.Column('excluded_unknown', sa.Integer(), nullable=False),
            sa.Column('error_type', sa.String(80)))
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_quotation_events')}
    for column in ['closes_at', 'snapshot_id']:
        name = 'ix_tvec_quotation_events_' + column
        if name not in indexes:
            op.create_index(name, 'tvec_quotation_events', [column])


def downgrade():
    bind = op.get_bind()
    for name in ['tvec_quotation_events', 'tvec_quotation_snapshots']:
        if sa.inspect(bind).has_table(name) and bind.execute(sa.text('SELECT 1 FROM '+name+' LIMIT 1')).first():
            raise RuntimeError('Preserve TVEC quotation data: populated downgrade forbidden')
    for name in ['tvec_quotation_snapshots', 'tvec_quotation_events']:
        if sa.inspect(bind).has_table(name):
            op.drop_table(name)
