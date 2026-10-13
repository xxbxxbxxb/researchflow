"""Opaque sessions, persistent login limits, idempotent starts and review decisions."""
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None
SQL = ['\nCREATE TABLE auth_sessions (\n\ttoken_hash VARCHAR(64) NOT NULL, \n\tactor_id VARCHAR(200) NOT NULL, \n\tcsrf_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (token_hash)\n)\n\n', '\nCREATE TABLE login_guards (\n\tsource_key VARCHAR(64) NOT NULL, \n\twindow_started TIMESTAMP WITH TIME ZONE NOT NULL, \n\tfailures INTEGER NOT NULL, \n\tpending INTEGER NOT NULL, \n\tPRIMARY KEY (source_key)\n)\n\n', '\nCREATE TABLE run_idempotency (\n\tproject_id VARCHAR(200) NOT NULL, \n\trequest_key VARCHAR(200) NOT NULL, \n\tpayload_hash VARCHAR(64) NOT NULL, \n\trun_id VARCHAR(200) NOT NULL, \n\tPRIMARY KEY (project_id, request_key), \n\tFOREIGN KEY(project_id, run_id) REFERENCES workflow_runs (project_id, run_id)\n)\n\n', '\nCREATE TABLE review_decisions (\n\tproject_id VARCHAR(200) NOT NULL, \n\trun_id VARCHAR(200) NOT NULL, \n\tdecision JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (project_id, run_id), \n\tFOREIGN KEY(project_id, run_id) REFERENCES workflow_runs (project_id, run_id)\n)\n\n']

def upgrade() -> None:
    for statement in SQL:
        op.execute(statement)

def downgrade() -> None:
    for table in ('review_decisions','run_idempotency','login_guards','auth_sessions'):
        op.execute('DROP TABLE IF EXISTS ' + table)
