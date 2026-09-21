from researchflow.ports.llm import LLMRequest,LLMResponse

class FakeLLM:
    def __init__(self,response_text: str) ->None:
        self._response_text = response_text
        self.last_request: LLMRequest | None =None
    async def generate(self, request:LLMRequest) ->LLMResponse:
        self.last_request = request
        
        return LLMResponse(
            text=self._response_text
        )