import json
from dataclasses import asdict

from researchflow.ports.model import ChatMessage, ChatRequest, ChatResponse
from researchflow.ports.retrieval import EmbeddingBatch
from researchflow.runtime.model_runtime import ModelRuntime


class EmbeddingAdapter:
    def __init__(self,provider):
        self.provider=provider
    async def complete(self,request):
        batch=await self.provider.embed(tuple(json.loads(request.messages[0].content)))
        return ChatResponse(json.dumps(asdict(batch)),model=batch.model)


class BudgetedEmbeddings:
    def __init__(self,provider,budgets,handle,context_window,trace):
        self.provider,self.model,self.dimensions=provider,provider.model,provider.dimensions
        self.handle=handle
        self.runtime=ModelRuntime(EmbeddingAdapter(provider),budgets,context_window,model_name=provider.model,trace=trace)
    async def embed(self,texts):
        response=await self.runtime.complete(self.handle,ChatRequest((ChatMessage('user',json.dumps(texts,ensure_ascii=False)),),operation='embedding_query',max_output_tokens=1))
        value=json.loads(response.text)
        return EmbeddingBatch(tuple(tuple(row) for row in value['vectors']),value['model'],value['dimensions'])
