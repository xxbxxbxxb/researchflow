"""Project/source lookup and lexical search indexes; variable vector namespaces are exact."""
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE INDEX ix_chunks_project_source ON chunks (project_id, snapshot_id)')
    op.execute("CREATE INDEX ix_chunks_english ON chunks USING gin (to_tsvector('simple', text))")
    op.execute('CREATE INDEX ix_chunks_trigram ON chunks USING gin (text gin_trgm_ops)')
    op.execute('CREATE INDEX ix_chunks_embedding_namespace ON chunks (project_id, embedding_version) WHERE embedding IS NOT NULL')


def downgrade() -> None:
    for name in ('ix_chunks_embedding_namespace','ix_chunks_trigram','ix_chunks_english','ix_chunks_project_source'):
        op.execute('DROP INDEX IF EXISTS ' + name)
