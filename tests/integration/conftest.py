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
    db = Database(url)
    await db.reset_for_test()
    yield db
    await db.close()


@pytest.fixture
def repository(database):
    from researchflow.infrastructure.storage.repositories import ResearchRepository
    return ResearchRepository(database)
