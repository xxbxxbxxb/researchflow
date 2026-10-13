import asyncio
import json
from dataclasses import asdict
from hashlib import sha256
from uuid import uuid4
from contextlib import suppress

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from researchflow.domain.access import Principal
from researchflow.domain.knowledge import FollowUpDraft
from researchflow.domain.projects import TaskRecord
from researchflow.domain.runs import RunHandle
from researchflow.domain.tool_calls import ToolCall, ToolResult
from researchflow.ports.sources import SourceInput
from researchflow.ports.runtime import RunCancelledError,RunOwnershipLostError
from researchflow.domain.usage import BudgetExceededError


class ToolAuthorizationError(ValueError):
    pass


class ToolArgumentsError(ToolAuthorizationError):
    pass


class QueryArgs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    query: str=Field(min_length=1,max_length=5000)


class FetchArgs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    url: str=Field(min_length=1,max_length=5000)


class InspectArgs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    evidence_id: str=Field(min_length=1,max_length=200)


class FollowUpArgs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    question: str=Field(min_length=1,max_length=5000)


ARGUMENTS={'search_sources':QueryArgs,'fetch_source':FetchArgs,'search_project':QueryArgs,'inspect_evidence':InspectArgs,'propose_follow_up':FollowUpArgs}


class ToolRegistry:
    def __init__(self, runs, budgets, search, ingestion, research, retriever):
        self.runs,self.budgets,self.search,self.ingestion,self.research,self.retriever=runs,budgets,search,ingestion,research,retriever
        self.locks={}
        self.schemas=tuple({'type':'function','function':{'name':name,'description':name.replace('_',' '),'parameters':args.model_json_schema()}} for name,args in ARGUMENTS.items())

    async def execute(self, handle: RunHandle, call: ToolCall, principal: Principal) -> ToolResult:
        if not principal.allows(handle.project_id) or call.name not in ARGUMENTS:
            raise ToolAuthorizationError('tool or project is not authorized')
        try:
            arguments=ARGUMENTS[call.name].model_validate(call.arguments).model_dump()
        except ValidationError as exc:
            raise ToolArgumentsError('invalid tool arguments; use only the advertised schema') from exc
        key=sha256(json.dumps([call.name,arguments],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        async with self.locks.setdefault((handle.run_id,key),asyncio.Lock()):
            old=await self.runs.get_tool(handle,key)
            if old is not None:
                return old
            budget=await self.budgets.reserve(handle,'tool')
            timeout=min(budget.limits.operation_timeout_seconds,budget.limits.active_timeout_seconds-budget.active_elapsed_seconds)
            operation_id=uuid4().hex
            slot=False
            try:
                async with asyncio.timeout(timeout):
                    while not slot:
                        slot=await self.budgets.acquire_slot(handle,operation_id,timeout)
                        if not slot:
                            await asyncio.sleep(0.01)
                    result=await self.dispatch(handle,call.name,arguments)
            except (TimeoutError,ValueError) as exc:
                result=ToolResult(call.name,{'message':'Source/tool operation could not be completed.'},error_code='source_unavailable' if isinstance(exc,ValueError) else 'tool_timeout')
            finally:
                if slot:
                    with suppress(RunOwnershipLostError,RunCancelledError):
                        await self.budgets.release_slot(handle,operation_id)
            return await self.runs.commit_tool(handle,key,result)

    async def dispatch(self, handle: RunHandle, name: str, args: dict) -> ToolResult:
        if name=='search_sources':
            candidates=await self.search.search(args['query'])
            return ToolResult(name,{'candidates':[{'source_id':c.source_id,'title':c.title,'url':c.url,'summary':c.summary[:1000]} for c in candidates]})
        if name=='fetch_source':
            prepared=await self.ingestion.prepare(handle.project_id,SourceInput(url=args['url']))
            return ToolResult(name,{'source_ids':[prepared.snapshot.snapshot_id]},(prepared.snapshot,))
        if name=='search_project':
            result=await self.retriever.search(handle.project_id,args['query'],())
            return ToolResult(name,{'source_ids':list(dict.fromkeys(c.snapshot_id for c in result.candidates)),'candidates':[asdict(c) for c in result.candidates]})
        if name=='inspect_evidence':
            item=await self.research.get_evidence(handle.project_id,args['evidence_id'])
            return ToolResult(name,{'evidence':asdict(item) if item else None})
        TaskRecord('draft',handle.project_id,args['question'])
        draft=FollowUpDraft(uuid4().hex,handle.project_id,handle.task_id,args['question'],())
        return ToolResult(name,{'draft_id':draft.draft_id},follow_up=draft)
