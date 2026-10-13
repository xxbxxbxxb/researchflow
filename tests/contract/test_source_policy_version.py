from types import SimpleNamespace

import pytest

from researchflow.domain.projects import TaskRecord
from researchflow.domain.runs import RunHandle
from researchflow.ports.runtime import InputVersionMismatchError
from researchflow.runtime.fixed_workflow import FixedWorkflow


@pytest.mark.asyncio
async def test_changed_source_policy_requires_new_run_before_any_phase_executes():
    class Runs:
        async def get_run(self,project,run):
            return SimpleNamespace(input_manifest={'workflow_version':'fixed-v1','execution_mode':'demo','code_version':'previous-policy'})
    class Research:
        async def get_task(self,project,task):
            return TaskRecord(task,project,'question')
    workflow=FixedWorkflow(Runs(),Research(),None,None,'demo')
    with pytest.raises(InputVersionMismatchError):
        await workflow.inputs(RunHandle('r','p','t',1,'w'))
