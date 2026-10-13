from dataclasses import replace

import pytest

from researchflow.application.evidence import anchor_evidence, manual_evidence
from researchflow.domain.errors import EvidenceConflict
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence


@pytest.mark.asyncio
async def test_actual_postgres_version_and_vector_extension(database):
    from sqlalchemy import text
    async with database.session() as session:
        version=await session.scalar(text('SHOW server_version_num'))
        extension=await session.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
    assert int(version)>=160000
    assert extension


@pytest.mark.asyncio
async def test_batch_conflict_rolls_back_new_records(repository):
    await repository.create_project(Project('p','Research'))
    snapshot,evidence=manual_evidence('p',Evidence('e1','paper','p1','Sample was 12. Second sentence.'))
    await repository.save_snapshot(snapshot)
    await repository.add_evidence_batch('p',(evidence,))
    fresh=anchor_evidence(snapshot,1,15,len(snapshot.pages[0].text))
    with pytest.raises(EvidenceConflict):
        await repository.add_evidence_batch('p',(fresh,replace(evidence,extractor_version='changed')))
    assert await repository.get_evidence('p',fresh.evidence.evidence_id) is None
    assert await repository.add_evidence_batch('p',(evidence,)) == (evidence,)


@pytest.mark.asyncio
async def test_project_scoped_foreign_keys_and_queries(repository):
    await repository.create_project(Project('p','Project'))
    await repository.create_project(Project('other','Other'))
    snapshot,evidence=manual_evidence('p',Evidence('same-id','paper','p1','Sample 12.'))
    await repository.save_snapshot(snapshot)
    await repository.add_evidence_batch('p',(evidence,))
    assert await repository.get_evidence('other','same-id') is None
    with pytest.raises(ValueError):
        await repository.add_evidence_batch('other',(evidence,))


@pytest.mark.asyncio
async def test_report_survives_engine_recreation(repository,database):
    from researchflow.application.research import ResearchService
    from researchflow.infrastructure.llm.demo_model import CASES, DemoCaseModel
    from researchflow.infrastructure.storage.database import Database
    from researchflow.infrastructure.storage.repositories import ResearchRepository
    await repository.create_project(Project('p','Research'))
    task=TaskRecord('t','p','What is the sample size?')
    await repository.save_task(task)
    snapshot,evidence=manual_evidence('p',Evidence('e1','synthetic','p1',CASES['supported']['source']))
    await repository.save_snapshot(snapshot)
    await repository.add_evidence_batch('p',(evidence,))
    result=await ResearchService(DemoCaseModel(),'demo').run_manual(task,(snapshot,),(evidence,),'run')
    await repository.save_result(result)
    reopened=Database(database.url)
    try:
        loaded=await ResearchRepository(reopened).get_result('p',result.report.report_id)
        assert loaded.report.markdown==result.report.markdown
        assert loaded.evidences[0].evidence.text==CASES['supported']['source']
    finally:
        await reopened.close()


def test_content_addressed_blob_storage_is_atomic_and_path_safe(tmp_path):
    import importlib
    if importlib.util.find_spec('researchflow.infrastructure.storage.blob_store') is None:
        pytest.fail('Content-addressed blob storage is not implemented')
    from researchflow.infrastructure.storage.blob_store import BlobStore
    store=BlobStore(tmp_path)
    first=store.put(b'research source')
    assert store.put(b'research source')==first
    assert store.get(first)==b'research source'
    with pytest.raises(ValueError):
        store.get('../../outside')
