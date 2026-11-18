"""Per-offer email reminders and durable saved opportunities."""
from alembic import op
import sqlalchemy as sa
revision='0018_offer_closing_reminders'
down_revision='0017_tvec_full_scan'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if 'is_saved' not in {c['name'] for c in sa.inspect(bind).get_columns('user_opportunities')}:
        op.add_column('user_opportunities',sa.Column('is_saved',sa.Boolean(),nullable=True))
    bind.execute(sa.text("UPDATE user_opportunities SET is_saved=CASE WHEN triage IN ('guardada','proyecto') THEN true ELSE false END WHERE is_saved IS NULL"))
    if not sa.inspect(bind).has_table('offer_closing_reminders'):
        op.create_table('offer_closing_reminders',
            sa.Column('project_id',sa.Integer(),sa.ForeignKey('offer_projects.id',ondelete='CASCADE'),primary_key=True),
            sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
            sa.Column('scheduled_at',sa.DateTime(),nullable=False),
            sa.Column('deadline_at',sa.DateTime(),nullable=False),sa.Column('retry_at',sa.DateTime()),
            sa.Column('recipient',sa.String(255),nullable=False),
            sa.Column('status',sa.String(20),nullable=False),
            sa.Column('attempts',sa.Integer(),nullable=False),
            sa.Column('claim_token',sa.String(36)),sa.Column('claimed_at',sa.DateTime()),
            sa.Column('sent_at',sa.DateTime()),sa.Column('last_error',sa.String(64)),
            sa.Column('updated_at',sa.DateTime(),nullable=False))
    indexes={i['name'] for i in sa.inspect(bind).get_indexes('offer_closing_reminders')}
    for column in ['user_id','scheduled_at','status']:
        name='ix_offer_closing_reminders_'+column
        if name not in indexes:op.create_index(name,'offer_closing_reminders',[column])

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM offer_closing_reminders LIMIT 1')).first():
        raise RuntimeError('Preserve scheduled email reminders: populated downgrade forbidden')
    if bind.execute(sa.text("SELECT 1 FROM user_opportunities WHERE (is_saved=true AND COALESCE(triage,'detectada') NOT IN ('guardada','proyecto')) OR (is_saved=false AND triage IN ('guardada','proyecto')) LIMIT 1")).first():
        raise RuntimeError('Preserve independent saved state: downgrade forbidden')
    op.drop_table('offer_closing_reminders')
    op.drop_column('user_opportunities','is_saved')
