import json
from dataclasses import asdict
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from researchflow.api.auth import require_project
from researchflow.api.errors import APIError
from researchflow.domain.runs import RunHandle
from researchflow.domain.usage import BudgetExceededError
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.infrastructure.llm.streaming import DemoStreamModel, OpenAIStreamModel
from researchflow.ports.model import ChatMessage, ChatRequest
from researchflow.ports.runtime import RunCancelledError, RunOwnershipLostError
from researchflow.runtime.model_runtime import ModelRuntime
from researchflow.runtime.streaming import StreamInterruptedError

router=APIRouter(tags=['preview'])


@router.post('/api/runs/{run_id}/preview',dependencies=[Depends(require_project)])
async def preview(run_id: str,project_id: str,request: Request):
    settings=request.app.state.settings
    if not settings.preview_enabled:
        raise APIError(409,'preview_disabled','Temporary generation preview is disabled.')
    resources=request.app.state.resources
    record=await resources.runs.get_run(project_id,run_id)
    if record is None or record.state!='running' or not record.owner_id:
        raise APIError(409,'run_not_active','Preview shares the active research budget and requires an active run.')
    mode=record.input_manifest['execution_mode']
    model=DemoStreamModel() if mode=='demo' else OpenAIStreamModel(resources.client,OpenAICompatibleConfig(settings.llm_base_url,settings.llm_api_key,settings.llm_model))
    from researchflow.runtime.budget import price_from_env
    runtime=ModelRuntime(model,resources.budgets,65536 if mode=='demo' else settings.context_window,price=price_from_env())
    handle=RunHandle(run_id,project_id,record.task_id,record.epoch,record.owner_id)
    preview_id=uuid4().hex
    async def events():
        seq=0
        iterator=runtime.stream(handle,ChatRequest((ChatMessage('system','This is an unverified temporary research planning preview, never a verified conclusion.'),ChatMessage('user',record.input_manifest['question'])),operation='preview'))
        try:
            async for delta in iterator:
                seq+=1
                event={'preview_id':preview_id,'seq':seq,'status':'completed' if delta.kind=='done' else 'unverified','execution_mode':mode,'delta':asdict(delta)}
                yield 'event: preview\ndata: '+json.dumps(event,ensure_ascii=False)+'\n\n'
        except (StreamInterruptedError,BudgetExceededError,RunOwnershipLostError,RunCancelledError):
            yield 'event: preview\ndata: '+json.dumps({'preview_id':preview_id,'seq':seq+1,'status':'incomplete','execution_mode':mode})+'\n\n'
        finally:
            await iterator.aclose()
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
