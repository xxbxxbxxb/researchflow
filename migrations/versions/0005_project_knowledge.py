"""Reviewed knowledge history and follow-up lineage."""
from alembic import op
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

SQL = (
    """CREATE TABLE knowledge_entries (
        project_id VARCHAR(200) NOT NULL,
        knowledge_id VARCHAR(200) NOT NULL,
        verification_id VARCHAR(200) NOT NULL,
        report_id VARCHAR(200) NOT NULL,
        status VARCHAR(30) NOT NULL,
        supersedes_id VARCHAR(200),
        data JSON NOT NULL,
        PRIMARY KEY (project_id,knowledge_id),
        FOREIGN KEY (project_id,verification_id) REFERENCES verifications(project_id,verification_id),
        FOREIGN KEY (project_id,report_id) REFERENCES report_versions(project_id,report_id),
        FOREIGN KEY (project_id,supersedes_id) REFERENCES knowledge_entries(project_id,knowledge_id)
    )""",
    """CREATE TABLE follow_up_drafts (
        project_id VARCHAR(200) NOT NULL,
        draft_id VARCHAR(200) NOT NULL,
        parent_task_id VARCHAR(200) NOT NULL,
        started_run_id VARCHAR(200),
        data JSON NOT NULL,
        PRIMARY KEY (project_id,draft_id),
        FOREIGN KEY (project_id,parent_task_id) REFERENCES research_tasks(project_id,task_id),
        FOREIGN KEY (project_id,started_run_id) REFERENCES workflow_runs(project_id,run_id)
    )""",
)

def upgrade() -> None:
    for statement in SQL:
        op.execute(statement)

def downgrade() -> None:
    for table in ('follow_up_drafts','knowledge_entries'):
        op.execute('DROP TABLE IF EXISTS ' + table)
