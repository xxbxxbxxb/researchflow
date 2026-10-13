import asyncio
import importlib
import json
from dataclasses import replace

import httpx
import pytest

from researchflow.domain.projects import Project,TaskRecord
from researchflow.ports.model import ChatMessage,ChatRequest,ChatResponse
from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig

REQUEST=ChatRequest((ChatMessage('user','A small fixture question.'),))


def modules():
    try:
        return importlib.import_module('researchflow.runtime.model_runtime'),importlib.import_module('researchflow.runtime.budget'),importlib.import_module('researchflow.infrastructure.storage.budget_repository')
    except ModuleNotFoundError:
        pytest.fail('durable model budget and usage runtime is not implemented')


async def setup(database,repository):
    modules()
    from researchflow.infrastructure.storage.run_repository import RunRepository
    await repository.create_project(Project('p','Budget project'))
    await repository.save_task(TaskRecord('t','p','Fixture question'))
    runs=RunRepository(database,repository)
    record=await runs.enqueue('t','p','fixed-v1',input_manifest={'execution_mode':'demo'})
    handle=await runs.claim_next('worker')
    return handle,runs


@pytest.mark.asyncio
async def test_retry_429_503_success_counts_every_raw_request_and_preserves_unknown_usage(database,repository):
    runtime_module,budget,storage=modules()
    handle,runs=await setup(database,repository)
    calls=[]
    def respond(request):
        calls.append(request)
        if len(calls)==1:
            return httpx.Response(429,headers={'retry-after':'0'},json={'error':'rate limited'})
        if len(calls)==2:
            return httpx.Response(503,json={'error':'unavailable'})
        return httpx.Response(200,json={'model':'fixture-model','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'Complete fixture response.'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model=OpenAIChatModel(client,OpenAICompatibleConfig('https://provider.test/v1','secret-test-key','fixture-model'))
        store=storage.BudgetRepository(database,runs)
        runtime=runtime_module.ModelRuntime(model,store,context_window=65536,random=lambda high:0.0)
        response=await runtime.complete(handle,REQUEST)
    assert len(calls)==3 and response.usage is None
    assert (await store.snapshot(handle)).model_calls_used==3
    records=await store.list_usage('p',handle.run_id)
    assert len(records)==3 and all(row['estimated_cost'] is None for row in records)
    assert 'secret-test-key' not in json.dumps(records)


@pytest.mark.asyncio
async def test_concurrent_attempts_cannot_send_request_seventeen(database,repository):
    runtime_module,budget,storage=modules()
    handle,runs=await setup(database,repository)
    class Provider:
        calls=0
        peak=0
        active=0
        async def complete(self,request):
            self.calls+=1
            self.active+=1
            self.peak=max(self.peak,self.active)
            try:
                await asyncio.sleep(0.005)
                return ChatResponse('ok',model='fixture')
            finally:
                self.active-=1
    provider=Provider()
    store=storage.BudgetRepository(database,runs)
    runtime=runtime_module.ModelRuntime(provider,store,context_window=65536)
    results=await asyncio.gather(*(runtime.complete(handle,replace(REQUEST,operation=op)) for op in ['claims']*8+['repair']*4+['verify']*4+['collect']*4),return_exceptions=True)
    assert provider.calls==16 and provider.peak<=4
    assert sum(isinstance(result,budget.BudgetExceededError) for result in results)==4
    assert (await store.snapshot(handle)).model_calls_used==16


@pytest.mark.asyncio
async def test_retry_after_is_not_ignored_when_it_exceeds_operation_deadline(database,repository):
    runtime_module,budget,storage=modules()
    handle,runs=await setup(database,repository)
    from researchflow.infrastructure.llm.errors import LLMProviderRateLimitError
    class Provider:
        calls=0
        async def complete(self,request):
            self.calls+=1
            raise LLMProviderRateLimitError('fixture retry',retry_after_seconds=120)
    provider=Provider()
    store=storage.BudgetRepository(database,runs,limits=budget.RunLimits(operation_timeout_seconds=1))
    runtime=runtime_module.ModelRuntime(provider,store,context_window=65536)
    with pytest.raises(budget.BudgetExceededError,match='operation'):
        await runtime.complete(handle,REQUEST)
    assert provider.calls==1


@pytest.mark.asyncio
async def test_actual_cancellation_closes_current_call_without_retry_or_refund(database,repository):
    runtime_module,budget,storage=modules()
    handle,runs=await setup(database,repository)
    entered=asyncio.Event()
    class Provider:
        calls=0
        cancelled=False
        async def complete(self,request):
            self.calls+=1
            entered.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.cancelled=True
                raise
    provider=Provider()
    store=storage.BudgetRepository(database,runs)
    runtime=runtime_module.ModelRuntime(provider,store,context_window=65536)
    task=asyncio.create_task(runtime.complete(handle,REQUEST))
    await asyncio.wait_for(entered.wait(),2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.calls==1 and provider.cancelled
    assert (await store.snapshot(handle)).model_calls_used==1


@pytest.mark.asyncio
async def test_context_capacity_and_versioned_cost_are_explicit(database,repository):
    runtime_module,budget,storage=modules()
    handle,runs=await setup(database,repository)
    from researchflow.domain.usage import ModelUsage
    class Provider:
        calls=0
        async def complete(self,request):
            self.calls+=1
            return ChatResponse('ok',model='fixture',usage=ModelUsage(1000,500))
    provider=Provider()
    store=storage.BudgetRepository(database,runs)
    runtime=runtime_module.ModelRuntime(provider,store,context_window=65536,price=budget.PriceConfig('fixture-usd-v1',1.0,2.0))
    assert (await runtime.complete(handle,REQUEST)).usage.estimated_cost==pytest.approx(0.002)
    with pytest.raises(budget.BudgetExceededError,match='context'):
        await runtime.complete(handle,replace(REQUEST,messages=(ChatMessage('user','x'*100000),)))
    assert provider.calls==1
