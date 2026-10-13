import os

import pytest


@pytest.fixture
async def database(tmp_path):
    url = os.getenv('RF_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Real PostgreSQL unavailable locally; required CI job runs this suite')
    import importlib
    if importlib.util.find_spec('researchflow.infrastructure.storage.database') is None:
        pytest.fail('PostgreSQL repository is not implemented')
    from researchflow.infrastructure.storage.database import Database
    from researchflow.infrastructure.storage.models import Base
    from sqlalchemy import text
    db = Database(url)
    async with db.engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.close()


@pytest.fixture
def repository(database):
    from researchflow.infrastructure.storage.repositories import ResearchRepository
    return ResearchRepository(database)
