"""Durable bounded full-list traversal; preserve existing published quotations."""
from alembic import op
import sqlalchemy as sa
revision='0017_tvec_full_scan'
down_revision='0016_tvec_quotations'
branch_labels=None
depends_on=None

def upgrade():
    if 'scan_progress' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('tvec_quotation_snapshots')}:
        op.add_column('tvec_quotation_snapshots',sa.Column('scan_progress',sa.JSON(),nullable=True))

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM tvec_quotation_snapshots WHERE scan_progress IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Preserve TVEC scan progress: populated downgrade forbidden')
    op.drop_column('tvec_quotation_snapshots','scan_progress')
