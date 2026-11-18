"""Separate TVEC purchase history; never touches SECOP/matching rows."""
from alembic import op
import sqlalchemy as sa

revision='0015_tvec_orders'
down_revision='0014_evaluation_platform'
branch_labels=None
depends_on=None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table('tvec_purchase_orders'):
        op.create_table('tvec_purchase_orders',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('official_id', sa.String(length=255), primary_key=False, nullable=False),
            sa.Column('source_row_id', sa.String(length=255), primary_key=False, nullable=False),
            sa.Column('buyer', sa.Text(), primary_key=False, nullable=True),
            sa.Column('buyer_nit', sa.String(length=100), primary_key=False, nullable=True),
            sa.Column('supplier', sa.Text(), primary_key=False, nullable=True),
            sa.Column('supplier_nit', sa.String(length=100), primary_key=False, nullable=True),
            sa.Column('description', sa.Text(), primary_key=False, nullable=True),
            sa.Column('instrument', sa.Text(), primary_key=False, nullable=True),
            sa.Column('category', sa.Text(), primary_key=False, nullable=True),
            sa.Column('department', sa.String(length=255), primary_key=False, nullable=True),
            sa.Column('city', sa.String(length=255), primary_key=False, nullable=True),
            sa.Column('amount', sa.Numeric(precision=30, scale=6), primary_key=False, nullable=True),
            sa.Column('currency', sa.String(length=3), primary_key=False, nullable=True),
            sa.Column('issued_at', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('expires_at', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('initial_request_at', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('status', sa.String(length=255), primary_key=False, nullable=True),
            sa.Column('official_url', sa.Text(), primary_key=False, nullable=True),
            sa.Column('raw_json', sa.JSON(), primary_key=False, nullable=False),
            sa.Column('version', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('seen_cycle', sa.String(length=36), primary_key=False, nullable=False),
            sa.Column('synced_at', sa.DateTime(), primary_key=False, nullable=False),
            sa.UniqueConstraint('official_id'),
        )
    if 'ix_tvec_purchase_orders_department' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_purchase_orders')}:
        op.create_index('ix_tvec_purchase_orders_department','tvec_purchase_orders',['department'],unique=False)
    if 'ix_tvec_purchase_orders_instrument' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_purchase_orders')}:
        op.create_index('ix_tvec_purchase_orders_instrument','tvec_purchase_orders',['instrument'],unique=False)
    if 'ix_tvec_purchase_orders_issued_at' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_purchase_orders')}:
        op.create_index('ix_tvec_purchase_orders_issued_at','tvec_purchase_orders',['issued_at'],unique=False)
    if 'ix_tvec_purchase_orders_seen_cycle' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_purchase_orders')}:
        op.create_index('ix_tvec_purchase_orders_seen_cycle','tvec_purchase_orders',['seen_cycle'],unique=False)
    if 'ix_tvec_purchase_orders_status' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_purchase_orders')}:
        op.create_index('ix_tvec_purchase_orders_status','tvec_purchase_orders',['status'],unique=False)
    if not sa.inspect(op.get_bind()).has_table('tvec_order_revisions'):
        op.create_table('tvec_order_revisions',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('tvec_purchase_orders.id'), primary_key=False, nullable=False),
            sa.Column('version', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('payload', sa.JSON(), primary_key=False, nullable=False),
            sa.Column('recorded_at', sa.DateTime(), primary_key=False, nullable=False),
        )
    if 'ix_tvec_order_revisions_order_id' not in {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('tvec_order_revisions')}:
        op.create_index('ix_tvec_order_revisions_order_id','tvec_order_revisions',['order_id'],unique=False)
    if not sa.inspect(op.get_bind()).has_table('tvec_source_metadata'):
        op.create_table('tvec_source_metadata',
            sa.Column('dataset_id', sa.String(length=20), primary_key=True, nullable=False),
            sa.Column('schema_hash', sa.String(length=64), primary_key=False, nullable=False),
            sa.Column('columns', sa.JSON(), primary_key=False, nullable=False),
            sa.Column('source_updated_at', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('checked_at', sa.DateTime(), primary_key=False, nullable=False),
            sa.Column('declared_frequency', sa.String(length=80), primary_key=False, nullable=True),
            sa.Column('source_count', sa.Integer(), primary_key=False, nullable=True),
        )
    if not sa.inspect(op.get_bind()).has_table('tvec_sync_states'):
        op.create_table('tvec_sync_states',
            sa.Column('dataset_id', sa.String(length=20), primary_key=True, nullable=False),
            sa.Column('cursor_id', sa.String(length=255), primary_key=False, nullable=True),
            sa.Column('cycle_id', sa.String(length=36), primary_key=False, nullable=False),
            sa.Column('cycle_rows', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('completed_cycles', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('source_generation', sa.String(length=64), primary_key=False, nullable=True),
            sa.Column('lease_token', sa.String(length=36), primary_key=False, nullable=True),
            sa.Column('lease_until', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('status', sa.String(length=24), primary_key=False, nullable=False),
            sa.Column('last_complete_at', sa.DateTime(), primary_key=False, nullable=True),
            sa.Column('error_count', sa.Integer(), primary_key=False, nullable=False),
        )
    if not sa.inspect(op.get_bind()).has_table('tvec_sync_runs'):
        op.create_table('tvec_sync_runs',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('state', sa.String(length=24), primary_key=False, nullable=False),
            sa.Column('max_pages', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('pages', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('processed', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('inserted', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('updated', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('unchanged', sa.Integer(), primary_key=False, nullable=False),
            sa.Column('error_type', sa.String(length=80), primary_key=False, nullable=True),
            sa.Column('created_at', sa.DateTime(), primary_key=False, nullable=False),
            sa.Column('finished_at', sa.DateTime(), primary_key=False, nullable=True),
        )

def downgrade():
    names=['tvec_purchase_orders', 'tvec_order_revisions', 'tvec_source_metadata', 'tvec_sync_states', 'tvec_sync_runs']
    for name in names:
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM "{name}"')).scalar():
            raise RuntimeError("Preserve TVEC history and metadata; use code/flags rollback")
    for name in reversed(names):op.drop_table(name)
