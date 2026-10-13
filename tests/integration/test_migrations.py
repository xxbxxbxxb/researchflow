import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_actual_migration_upgrade_downgrade_upgrade(database):
    from researchflow.infrastructure.storage.models import Base
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
    env={**os.environ,'RF_DATABASE_URL':database.url}
    for target in ['head','base','head']:
        result=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic','downgrade' if target=='base' else 'upgrade',target],capture_output=True,text=True,env=env)
        assert result.returncode==0,result.stderr
    async with database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_name='report_versions'")) == 1
        assert await session.scalar(text('SELECT version_num FROM alembic_version'))
