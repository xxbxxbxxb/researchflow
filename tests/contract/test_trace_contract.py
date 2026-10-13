import importlib
import json

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from researchflow.domain.runs import RunHandle
from researchflow.infrastructure.llm.errors import LLMProviderUnavailableError
from researchflow.ports.model import ChatMessage, ChatRequest, ChatResponse
from researchflow.runtime.budget import MemoryBudgetRepository
from researchflow.runtime.model_runtime import ModelRuntime


def module():
    try:
        return importlib.import_module('researchflow.infrastructure.telemetry.otel')
    except ModuleNotFoundError:
        pytest.fail('business-independent OTel tracing is not implemented')


@pytest.mark.asyncio
async def test_real_otel_parentage_attempts_and_default_redaction():
    telemetry=module()
    exporter=InMemorySpanExporter()
    trace=telemetry.OpenTelemetryTrace(exporter=exporter)
    h=RunHandle('r','p','t',1,'w')
    class Provider:
        calls=0
        async def complete(self,request):
            self.calls+=1
            if self.calls==1:
                raise LLMProviderUnavailableError('retry')
            return ChatResponse('ok',model='fixture')
    runtime=ModelRuntime(Provider(),MemoryBudgetRepository(h),65536,random=lambda high:0,trace=trace)
    with trace.span('research.run',{'run_id':'r','task_id':'t','api_key':'secret-test-key','source_text':'private source content'}):
        await runtime.complete(h,ChatRequest((ChatMessage('user','private prompt'),),operation='claims'))
    spans=exporter.get_finished_spans()
    root=next(s for s in spans if s.name=='research.run')
    model=next(s for s in spans if s.name=='model')
    attempts=[s for s in spans if s.name=='model.attempt']
    assert model.parent.span_id==root.context.span_id
    assert len(attempts)==2 and all(a.parent.span_id==model.context.span_id for a in attempts)
    assert len({a.attributes['attempt_id'] for a in attempts})==2
    assert all(a.attributes['step_id']=='claims' for a in attempts)
    serialized=json.dumps([dict(s.attributes) for s in spans])
    assert 'secret-test-key' not in serialized and 'private source content' not in serialized and 'private prompt' not in serialized
    trace.close()


def test_failing_exporter_never_prevents_already_committed_business_result():
    telemetry=module()
    from opentelemetry.sdk.trace.export import SpanExporter
    class Broken(SpanExporter):
        def export(self,spans):
            raise RuntimeError('export unavailable')
    trace=telemetry.OpenTelemetryTrace(exporter=Broken())
    business=[]
    with trace.span('business.step',{'run_id':'r'}):
        business.append('committed-evidence')
    assert business==['committed-evidence']
    trace.close()
