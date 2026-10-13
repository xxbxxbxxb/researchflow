"""Fenced tool results."""
from alembic import op
import sqlalchemy as sa

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('tool_receipts',sa.Column('project_id',sa.String(200),primary_key=True),sa.Column('run_id',sa.String(200),primary_key=True),sa.Column('call_key',sa.String(64),primary_key=True),sa.Column('output',sa.JSON(),nullable=False),sa.Column('committed_at',sa.DateTime(timezone=True),nullable=False),sa.ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']))


def downgrade():
    op.drop_table('tool_receipts')
