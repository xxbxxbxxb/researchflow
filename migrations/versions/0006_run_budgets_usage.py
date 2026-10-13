"""Durable budget counters, per-attempt usage and bounded external operation slots."""
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

SQL = (
    """CREATE TABLE run_budgets (
        project_id VARCHAR(200) NOT NULL, run_id VARCHAR(200) NOT NULL,
        limits JSON NOT NULL, model_calls_used INTEGER NOT NULL,
        tool_calls_used INTEGER NOT NULL, steps_used INTEGER NOT NULL,
        active_elapsed_seconds DOUBLE PRECISION NOT NULL,
        active_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
        active_epoch INTEGER NOT NULL, active BOOLEAN NOT NULL,
        PRIMARY KEY (project_id,run_id),
        FOREIGN KEY (project_id,run_id) REFERENCES workflow_runs(project_id,run_id)
    )""",
    """CREATE TABLE model_usage (
        project_id VARCHAR(200) NOT NULL, run_id VARCHAR(200) NOT NULL,
        attempt_id VARCHAR(200) NOT NULL, epoch INTEGER NOT NULL,
        operation VARCHAR(100) NOT NULL, model VARCHAR(200) NOT NULL, status VARCHAR(40) NOT NULL,
        input_tokens BIGINT, output_tokens BIGINT, estimated_cost DOUBLE PRECISION,
        price_version VARCHAR(200), request_id VARCHAR(200),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL, completed_at TIMESTAMP WITH TIME ZONE,
        PRIMARY KEY (project_id,run_id,attempt_id),
        FOREIGN KEY (project_id,run_id) REFERENCES workflow_runs(project_id,run_id)
    )""",
    """CREATE TABLE operation_slots (
        project_id VARCHAR(200) NOT NULL, run_id VARCHAR(200) NOT NULL,
        operation_id VARCHAR(200) NOT NULL, epoch INTEGER NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        PRIMARY KEY (project_id,run_id,operation_id),
        FOREIGN KEY (project_id,run_id) REFERENCES workflow_runs(project_id,run_id)
    )""",
)

def upgrade() -> None:
    for statement in SQL:
        op.execute(statement)

def downgrade() -> None:
    for table in ('operation_slots','model_usage','run_budgets'):
        op.execute('DROP TABLE IF EXISTS ' + table)
