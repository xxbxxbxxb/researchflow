import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal
from uuid import uuid4
from dataclasses import dataclass

import httpx

from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.demo_model import DemoCaseModel
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.repositories import ResearchRepository
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.ports.runtime import InputVersionMismatchError
from researchflow.runtime.fixed_workflow import FixedWorkflow
from researchflow.runtime.worker import Worker


class ConfiguredWorkflow:
    def __init__(self, runs, research, retriever, model, mode):
        self.runs,self.research,self.retriever,self.model,self.mode = runs,research,retriever,model,mode

    async def execute(self, handle):
        record = await self.runs.get_run(handle.project_id,handle.run_id)
        if record is None or record.input_manifest['execution_mode'] != self.mode:
            raise InputVersionMismatchError('worker mode differs from persisted run input')
        model = DemoCaseModel(record.input_manifest.get('demo_case','supported')) if self.mode == 'demo' else self.model
        return await FixedWorkflow(self.runs,self.research,self.retriever,model,self.mode).execute(handle)


@asynccontextmanager
async def worker_resources(mode: Literal['demo','live'], owner_id: str | None = None):
    url = os.getenv('RF_DATABASE_URL')
    if not url:
        raise ValueError('RF_DATABASE_URL is required for the persistent Worker')
    if mode == 'live' and not all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL')):
        raise ValueError('Live mode requires RF_LLM_BASE_URL, RF_LLM_API_KEY and RF_LLM_MODEL')
    async with AsyncExitStack() as stack:
        database = Database(url)
        stack.push_async_callback(database.close)
        client = await stack.enter_async_context(httpx.AsyncClient(timeout=60,trust_env=False))
        model = OpenAIChatModel(client,OpenAICompatibleConfig(os.environ['RF_LLM_BASE_URL'],os.environ['RF_LLM_API_KEY'],os.environ['RF_LLM_MODEL'])) if mode == 'live' else DemoCaseModel()
        research = ResearchRepository(database)
        runs = RunRepository(database,research)
        workflow = ConfiguredWorkflow(runs,research,PostgresRetriever(database),model,mode)
        yield Worker(runs,workflow,owner_id or 'worker-' + uuid4().hex)


@dataclass
class APIResources:
    database: Database
    research: ResearchRepository
    runs: RunRepository
    retriever: PostgresRetriever
    sessions: object
    blobs: object
    ingestion: object
    client: httpx.AsyncClient
    knowledge: object
    knowledge_repository: object


@asynccontextmanager
async def api_resources(settings, database: Database | None = None):
    from researchflow.application.ingestion import IngestSource
    from researchflow.application.knowledge import KnowledgeService
    from researchflow.infrastructure.storage.knowledge_repository import KnowledgeRepository
    from researchflow.infrastructure.sources.parsers import DocumentParser
    from researchflow.infrastructure.sources.safe_http import SourceFetcher
    from researchflow.infrastructure.storage.blob_store import BlobStore
    from researchflow.infrastructure.storage.session_repository import SessionRepository
    async with AsyncExitStack() as stack:
        db = database or Database(settings.database_url)
        if database is None:
            stack.push_async_callback(db.close)
        client = await stack.enter_async_context(httpx.AsyncClient(timeout=60,trust_env=False))
        research = ResearchRepository(db)
        blobs = BlobStore(settings.blob_root)
        retriever = PostgresRetriever(db)
        knowledge_repository = KnowledgeRepository(db,research)
        yield APIResources(db,research,RunRepository(db,research),retriever,SessionRepository(db),blobs,IngestSource(research,blobs,DocumentParser(),SourceFetcher()),client,KnowledgeService(knowledge_repository),knowledge_repository)
