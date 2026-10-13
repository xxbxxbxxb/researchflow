import importlib
from pathlib import Path

import pytest

from researchflow.domain.projects import Project, TaskRecord


def retrieval_module():
    try:
        return importlib.import_module('researchflow.infrastructure.storage.retrieval')
    except ModuleNotFoundError:
        pytest.fail('project retrieval not implemented')


async def ingest(repository, tmp_path, project, text, filename='notes.md'):
    from researchflow.application.ingestion import IngestSource
    from researchflow.infrastructure.sources.parsers import DocumentParser
    from researchflow.infrastructure.storage.blob_store import BlobStore
    from researchflow.ports.sources import SourceInput
    await repository.create_project(Project(project, project, ''))
    service = IngestSource(repository, BlobStore(tmp_path/'blobs'), DocumentParser())
    return await service.execute(project, SourceInput(filename=filename, data=text.encode(), media_type='text/markdown'))


@pytest.mark.asyncio
async def test_project_scoped_chinese_english_lexical_and_no_invented_results(database, repository, tmp_path):
    m = retrieval_module()
    text = '中文实验样本为十二个。English experiment enrolled twelve participants.\n\n' + 'unrelated context ' * 100
    snapshot = await ingest(repository, tmp_path, 'a', text)
    other = await ingest(repository, tmp_path, 'b', text)
    retriever = m.PostgresRetriever(database)
    await retriever.index_snapshot(snapshot)
    await retriever.index_snapshot(other)
    for query in ('中文实验样本', 'experiment participants'):
        result = await retriever.search('a', query, (snapshot.snapshot_id,))
        assert result.mode == 'lexical' and result.embedding_version is None
        assert result.candidates and len(result.candidates) <= 8
        assert all(c.project_id == 'a' and c.snapshot_id == snapshot.snapshot_id for c in result.candidates)
        assert '十二个' in result.candidates[0].text
    assert not (await retriever.search('a', 'zzzzzzzzzzzz', (snapshot.snapshot_id,))).candidates
    assert not (await retriever.search('a', '实验', (other.snapshot_id,))).candidates


@pytest.mark.asyncio
async def test_pgvector_hybrid_and_index_version_cannot_be_mixed(database, repository, tmp_path):
    m = retrieval_module()
    from researchflow.ports.retrieval import EmbeddingBatch
    class Embed:
        model = 'fixed-vector-fixture'
        dimensions = 2
        async def embed(self, texts):
            return EmbeddingBatch(tuple((1.0,0.1) if 'experiment' in text else (0.1,1.0) for text in texts), self.model, self.dimensions)
    embed = Embed()
    snapshot = await ingest(repository, tmp_path, 'p', 'experiment correct result\n\n' + 'background ' * 150)
    retriever = m.PostgresRetriever(database, embed)
    await retriever.index_snapshot(snapshot)
    result = await retriever.search('p', 'experiment', (snapshot.snapshot_id,))
    assert result.mode == 'hybrid' and result.embedding_version == 'fixed-vector-fixture:2:chunks-800-100-v1'
    assert 'correct result' in result.candidates[0].text
    embed.dimensions = 3
    with pytest.raises(ValueError, match='index_version_mismatch'):
        await retriever.search('p', 'experiment', (snapshot.snapshot_id,))


@pytest.mark.asyncio
async def test_pdf_to_retrieved_anchored_evidence_report_survives_reopen(database, repository, tmp_path):
    m = retrieval_module()
    from researchflow.application.ingestion import IngestSource
    from researchflow.application.retrieval import EvidenceSelector
    from researchflow.application.claims import ClaimExtractor
    from researchflow.application.verification import ClaimVerifier
    from researchflow.application.reports import ReportBuilder
    from researchflow.application.evidence import validate_anchor
    from researchflow.domain.reports import ReportInputs, ResearchResult
    from researchflow.ports.model import ChatResponse
    import json
    from researchflow.infrastructure.sources.parsers import DocumentParser
    from researchflow.infrastructure.storage.blob_store import BlobStore
    from researchflow.infrastructure.storage.database import Database
    from researchflow.infrastructure.storage.repositories import ResearchRepository
    from researchflow.ports.sources import SourceInput
    await repository.create_project(Project('p','PDF project',''))
    blob = BlobStore(tmp_path/'blobs')
    source = await IngestSource(repository,blob,DocumentParser()).execute('p',SourceInput(filename='paper.pdf',data=(Path(__file__).parents[1]/'fixtures/sources/chinese-two-pages.pdf').read_bytes(),media_type='application/pdf'))
    task = TaskRecord('t','p','中文实验样本',(source.snapshot_id,))
    await repository.save_task(task)
    retriever = m.PostgresRetriever(database)
    await retriever.index_snapshot(source)
    found = await retriever.search('p', task.question, task.source_ids)
    evidence = EvidenceSelector().select(found)
    assert evidence
    for item in evidence:
        validate_anchor(item,source)
    await repository.add_evidence_batch('p',evidence)
    class PDFFixtureModel:
        async def complete(self, request):
            data = json.loads(request.messages[1].content)
            refs = [e['evidence_id'] for e in data['evidence']]
            if request.operation == 'claims':
                payload = {'claims':[{'text':'中文实验样本为十二个','evidence_ids':refs,'qualifiers':[]}]}
            else:
                payload = {'verifications':[{'claim_id':c['claim_id'],'status':'supported','evidence_ids':refs,'quotes':[{'evidence_id':e['evidence_id'],'quote':e['text']} for e in data['evidence']],'rationale':'Explicit deterministic PDF fixture, not model quality.'} for c in data['claims']]}
            return ChatResponse(json.dumps(payload,ensure_ascii=False),model='demo:pdf-fixture')
    model = PDFFixtureModel()
    claims = await ClaimExtractor(model).extract(task,evidence)
    verification = await ClaimVerifier(model).verify(claims,evidence,(source,))
    report = ReportBuilder().build(ReportInputs('p','t','run',claims,verification,evidence,(),task.question,'demo'))
    assert report.conclusion_claim_ids
    result = ResearchResult('p','t','run',report,claims,verification,evidence,(),'demo')
    await repository.save_result(result)
    saved = await repository.get_result('p',report.report_id)
    reopened = Database(str(database.engine.url.render_as_string(hide_password=False)))
    try:
        loaded = await ResearchRepository(reopened).get_result('p',saved.report.report_id)
        assert loaded == saved
        assert blob.get(source.content_hash).startswith(b'%PDF')
    finally:
        await reopened.close()
