import json
import httpx
from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.errors import LLMProviderUnavailableError,LLMProviderProtocolError
from researchflow.domain.tool_calls import ToolCall
from researchflow.domain.usage import ModelUsage
from researchflow.ports.model import ModelDelta


async def sse_data(response):
    buffer=b''
    data=[]
    async for chunk in response.aiter_bytes():
        buffer+=chunk
        if len(buffer)>1024*1024:
            raise LLMProviderProtocolError('SSE event exceeds size limit')
        while b'\n' in buffer:
            raw,buffer=buffer.split(b'\n',1)
            line=raw.rstrip(b'\r').decode('utf-8',errors='strict')
            if not line:
                if data:
                    yield '\n'.join(data)
                    data=[]
            elif line.startswith('data:'):
                data.append(line[5:].lstrip(' '))
                if sum(len(x) for x in data)>1024*1024:
                    raise LLMProviderProtocolError('SSE event exceeds size limit')
    # A truncated final frame is not an explicit [DONE] signal.


class OpenAIStreamModel(OpenAIChatModel):
    async def stream(self,request):
        body=self.request_body(request)
        body.update(stream=True,stream_options={'include_usage':True})
        tools={}
        try:
            async with self.client.stream('POST',self.config.base_url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+self.config.api_key},json=body) as response:
                self.check_status(response)
                async for event in sse_data(response):
                    if event=='[DONE]':
                        yield ModelDelta('done')
                        return
                    try:
                        value=json.loads(event)
                        if value.get('error'):
                            raise LLMProviderProtocolError('provider sent a streaming error')
                        if value.get('usage'):
                            raw=value['usage']
                            yield ModelDelta('usage',usage=ModelUsage(raw.get('prompt_tokens'),raw.get('completion_tokens')))
                        for choice in value.get('choices',[]):
                            delta=choice.get('delta',{})
                            if delta.get('refusal') or choice.get('finish_reason') in ('length','content_filter'):
                                raise LLMProviderProtocolError('provider streaming output refused or truncated')
                            if isinstance(delta.get('content'),str) and delta['content']:
                                yield ModelDelta('text',delta['content'])
                            for row in delta.get('tool_calls',[]):
                                saved=tools.setdefault(row['index'],{'id':'','name':'','arguments':''})
                                saved['id']+=row.get('id','')
                                fn=row.get('function',{})
                                saved['name']+=fn.get('name','')
                                saved['arguments']+=fn.get('arguments','')
                                if len(saved['arguments'])>65536:
                                    raise ValueError('tool parameters exceed bound')
                            if choice.get('finish_reason')=='tool_calls':
                                for saved in tools.values():
                                    arguments=json.loads(saved['arguments'])
                                    if not isinstance(arguments,dict) or not saved['id'] or not saved['name']:
                                        raise ValueError('tool call is incomplete')
                                    yield ModelDelta('tool_call',tool_call=ToolCall(saved['id'],saved['name'],arguments))
                                tools.clear()
                    except (TypeError,ValueError,KeyError) as exc:
                        raise LLMProviderProtocolError('invalid streamed provider protocol') from exc
        except httpx.TransportError as exc:
            raise LLMProviderUnavailableError('provider streaming transport failed') from exc


class DemoStreamModel:
    async def stream(self,request):
        yield ModelDelta('text','固定演示预览：临时生成内容，尚未经过证据验证。')
        yield ModelDelta('done')
