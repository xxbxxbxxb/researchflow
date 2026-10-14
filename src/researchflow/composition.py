import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import httpx

from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.demo_model import DemoCaseModel
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.infrastructure.storage.budget_repository import BudgetRepository
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.repositories import ResearchRepository
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.ports.runtime import InputVersionMismatchError
from researchflow.runtime.budgeted_runs import BudgetedRuns
from researchflow.runtime.fixed_workflow import FixedWorkflow
from researchflow.runtime.model_runtime import BoundChatModel, ModelRuntime
from researchflow.runtime.worker import Worker


def configured_embeddings(settings,client):
    if not settings.embedding_configured:
        return None
    from researchflow.infrastructure.llm.embeddings import OpenAIEmbeddings
    return OpenAIEmbeddings(client,settings.embedding_base_url,settings.embedding_api_key,settings.embedding_model,settings.embedding_dimensions)


class ConfiguredWorkflow:
    def __init__(self, runs, research, retriever, model, mode, context_window: int | None = None, price=None,trace=None):
        self.runs,self.research,self.retriever,self.model,self.mode=runs,research,retriever,model,mode
        self.context_window,self.price=context_window,price
        self.runtimes: dict[tuple[str,int],ModelRuntime]={}
        from researchflow.ports.telemetry import NullTrace
        self.trace=trace or NullTrace()

    async def tick(self, handle):
        runtime=self.runtimes.get((handle.run_id,handle.epoch))
        if runtime is not None:
            await runtime.tick(handle)

    async def execute(self, handle):
        record=await self.runs.get_run(handle.project_id,handle.run_id)
        if record is None:
            raise InputVersionMismatchError('persisted run input is missing')
        mode=record.input_manifest['execution_mode']
        if mode=='live' and isinstance(self.model,DemoCaseModel):
            raise InputVersionMismatchError('live provider is not configured for this Worker')
        if mode=='live' and getattr(self.model,'config',None) is not None:
            actual=self.model.config.model
            if record.input_manifest['model_version']!=actual or record.input_manifest.get('context_window')!=self.context_window:
                raise InputVersionMismatchError('model or context policy changed; create a new run')
        model=DemoCaseModel(record.input_manifest.get('demo_case','supported')) if mode=='demo' else self.model
        from researchflow.domain.usage import RunLimits
        store=BudgetRepository(self.runs.database,self.runs,RunLimits(**record.input_manifest.get('limits',{})))
        context=self.context_window if mode=='live' else 65536
        runtime=ModelRuntime(model,store,context_window=context,price=self.price,model_name=record.input_manifest.get('model_version','configured'),trace=self.trace)
        key=(handle.run_id,handle.epoch)
        self.runtimes[key]=runtime
        try:
            await runtime.tick(handle)
            retriever=self.retriever
            if mode=='live' and self.retriever.embeddings:
                from researchflow.runtime.embedding_runtime import BudgetedEmbeddings
                retriever=PostgresRetriever(self.runs.database,BudgetedEmbeddings(self.retriever.embeddings,store,handle,context,self.trace))
            from researchflow.runtime.graph_workflow import GraphWorkflow
            driver=GraphWorkflow if record.input_manifest['workflow_version']=='graph-v1' else FixedWorkflow
            collector=None
            if record.input_manifest.get('collect_sources'):
                from pathlib import Path

                from researchflow.application.ingestion import IngestSource
                from researchflow.domain.access import Principal
                from researchflow.infrastructure.sources.arxiv import ArxivSearch
                from researchflow.infrastructure.sources.parsers import DocumentParser
                from researchflow.infrastructure.sources.safe_http import SourceFetcher
                from researchflow.infrastructure.storage.blob_store import BlobStore
                from researchflow.runtime.react import MinimalReAct
                from researchflow.runtime.tools import ToolRegistry
                fetcher=SourceFetcher()
                ingestion=IngestSource(self.research,BlobStore(Path(os.getenv('RF_BLOB_ROOT','.researchflow-data/blobs'))),DocumentParser(),fetcher)
                registry=ToolRegistry(self.runs,store,ArxivSearch(fetcher),ingestion,self.research,retriever)
                collector=MinimalReAct(BoundChatModel(runtime,handle),registry,store,Principal('owner',(handle.project_id,)))
            from researchflow.infrastructure.storage.knowledge_repository import KnowledgeRepository
            knowledge=KnowledgeRepository(self.runs.database,self.research)
            return await driver(BudgetedRuns(self.runs,runtime),self.research,retriever,BoundChatModel(runtime,handle),mode,collector,trace=self.trace,knowledge=knowledge).execute(handle)
        finally:
            self.runtimes.pop(key,None)


@asynccontextmanager
async def worker_resources(mode: Literal['demo','live'], owner_id: str | None = None):
    url = os.getenv('RF_DATABASE_URL')
    if not url:
        raise ValueError('RF_DATABASE_URL is required for the persistent Worker')
    if mode == 'live' and not all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL','RF_CONTEXT_WINDOW')):
        raise ValueError('Live mode requires provider credentials and RF_CONTEXT_WINDOW')
    async with AsyncExitStack() as stack:
        database = Database(url)
        stack.push_async_callback(database.close)
        client = await stack.enter_async_context(httpx.AsyncClient(timeout=60,trust_env=False))
        live_available=all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL','RF_CONTEXT_WINDOW'))
        model = OpenAIChatModel(client,OpenAICompatibleConfig(os.environ['RF_LLM_BASE_URL'],os.environ['RF_LLM_API_KEY'],os.environ['RF_LLM_MODEL'])) if live_available else DemoCaseModel()
        research = ResearchRepository(database)
        runs = RunRepository(database,research)
        from researchflow.settings import Settings
        retriever=PostgresRetriever(database,configured_embeddings(Settings.from_env(),client) if live_available else None)
        from researchflow.infrastructure.telemetry.otel import OpenTelemetryTrace
        trace=OpenTelemetryTrace(endpoint=os.getenv('RF_OTLP_TRACES_ENDPOINT'))
        stack.callback(trace.close)
        from researchflow.runtime.budget import price_from_env
        workflow = ConfiguredWorkflow(runs,research,retriever,model,mode,context_window=int(os.environ['RF_CONTEXT_WINDOW']) if live_available else None,trace=trace,price=price_from_env())
        yield Worker(runs,workflow,owner_id or 'worker-' + uuid4().hex,on_heartbeat=workflow.tick,trace=trace)


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
    budgets: BudgetRepository


@asynccontextmanager
async def api_resources(settings, database: Database | None = None):
    from researchflow.application.ingestion import IngestSource
    from researchflow.application.knowledge import KnowledgeService
    from researchflow.infrastructure.sources.parsers import DocumentParser
    from researchflow.infrastructure.sources.safe_http import SourceFetcher
    from researchflow.infrastructure.storage.blob_store import BlobStore
    from researchflow.infrastructure.storage.knowledge_repository import KnowledgeRepository
    from researchflow.infrastructure.storage.session_repository import SessionRepository
    async with AsyncExitStack() as stack:
        db = database or Database(settings.database_url)
        if database is None:
            stack.push_async_callback(db.close)
        client = await stack.enter_async_context(httpx.AsyncClient(timeout=60,trust_env=False))
        research = ResearchRepository(db)
        blobs = BlobStore(settings.blob_root)
        retriever = PostgresRetriever(db,configured_embeddings(settings,client) if settings.execution_mode=='live' else None)
        knowledge_repository = KnowledgeRepository(db,research)
        yield APIResources(db,research,RunRepository(db,research),retriever,SessionRepository(db),blobs,IngestSource(research,blobs,DocumentParser(),SourceFetcher()),client,KnowledgeService(knowledge_repository),knowledge_repository,BudgetRepository(db))
