"""JSON graph checkpoints and pending writes with project/run ownership."""
from alembic import op
import sqlalchemy as sa

revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('graph_checkpoints',sa.Column('project_id',sa.String(200),primary_key=True),sa.Column('run_id',sa.String(200),primary_key=True),sa.Column('namespace',sa.String(500),primary_key=True),sa.Column('checkpoint_id',sa.String(100),primary_key=True),sa.Column('parent_id',sa.String(100)),sa.Column('input_version',sa.String(200),nullable=False),sa.Column('checkpoint_data',sa.Text(),nullable=False),sa.Column('metadata_data',sa.Text(),nullable=False),sa.ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']))
    op.create_table('graph_writes',sa.Column('project_id',sa.String(200),primary_key=True),sa.Column('run_id',sa.String(200),primary_key=True),sa.Column('namespace',sa.String(500),primary_key=True),sa.Column('checkpoint_id',sa.String(100),primary_key=True),sa.Column('task_id',sa.String(200),primary_key=True),sa.Column('idx',sa.Integer(),primary_key=True),sa.Column('channel',sa.String(500),nullable=False),sa.Column('task_path',sa.Text(),nullable=False),sa.Column('value_data',sa.Text(),nullable=False),sa.ForeignKeyConstraint(['project_id','run_id','namespace','checkpoint_id'],['graph_checkpoints.project_id','graph_checkpoints.run_id','graph_checkpoints.namespace','graph_checkpoints.checkpoint_id'],ondelete='CASCADE'))


def downgrade():
    op.drop_table('graph_writes')
    op.drop_table('graph_checkpoints')
