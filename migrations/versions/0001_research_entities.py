from alembic import op
from researchflow.infrastructure.storage.models import Base

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

INITIAL_TABLES = ('projects','research_tasks','source_snapshots','snapshot_pages','documents','chunks','evidences','claims','claim_evidence_links','verifications','report_versions')


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    Base.metadata.create_all(op.get_bind(),tables=[Base.metadata.tables[name] for name in INITIAL_TABLES])


def downgrade():
    Base.metadata.drop_all(op.get_bind(),tables=[Base.metadata.tables[name] for name in INITIAL_TABLES])
