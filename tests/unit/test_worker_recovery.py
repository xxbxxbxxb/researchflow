import pytest

from researchflow.domain.runs import RunHandle, RunOutcome
from researchflow.runtime.worker import Worker


@pytest.mark.asyncio
async def test_worker_recovers_expired_run_when_queue_is_empty():
    handle = RunHandle('run', 'p', 't', 2, 'worker')
    class Runs:
        recovered = False
        final = None
        async def claim_next(self, owner):
            return None
        async def recover_expired(self, owner):
            self.recovered = True
            return handle
        async def finish(self, h, state, error=None):
            self.final = state
    class Workflow:
        async def execute(self, h):
            assert h == handle
            return RunOutcome('succeeded')
    runs = Runs()
    assert await Worker(runs, Workflow(), 'worker').run_once()
    assert runs.recovered and runs.final == 'succeeded'

