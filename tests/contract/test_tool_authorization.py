import importlib
import pytest
from researchflow.domain.access import Principal
from researchflow.domain.runs import RunHandle
from researchflow.domain.tool_calls import ToolCall


def tools_module():
    try:
        return importlib.import_module('researchflow.runtime.tools')
    except ModuleNotFoundError:
        pytest.fail('tool authorization boundary is not implemented')


@pytest.mark.asyncio
@pytest.mark.parametrize('name,args,principal', [
    ('shell', {'command': 'whoami'}, Principal('owner')),
    ('fetch_source', {'url': 'https://example.org', 'project_id': 'other'}, Principal('owner')),
    ('fetch_source', {'url': 'https://example.org'}, Principal('limited', ('other',))),
])
async def test_denied_tool_never_reaches_external_or_storage_side_effect(name, args, principal):
    tools = tools_module()
    class Forbidden:
        def __getattr__(self, name):
            pytest.fail('denied call reached a dependency')
    registry = tools.ToolRegistry(Forbidden(), Forbidden(), Forbidden(), Forbidden(), Forbidden(), Forbidden())
    with pytest.raises(tools.ToolAuthorizationError):
        await registry.execute(RunHandle('r','p','t',1,'w'), ToolCall('x',name,args), principal)

