from researchflow.ports.llm import LLMPort,LLMRequest

MAX_QUESTION_LENGTH = 5000

class AskResearchQuestion:
    def __init__(self,llm:LLMPort) ->None:
        self._llm = llm
    
    async def execute(self,question: str)->str:
        clean_question = question.strip()
        
        if not clean_question:
            raise ValueError("question must not be empty")
        if len(clean_question)>MAX_QUESTION_LENGTH:
            raise ValueError(f"question must not exceed {MAX_QUESTION_LENGTH} characters")
        
        request = LLMRequest(
            prompt=(
                "You are a research assistant. "
                "Answer the following technical research question concisely:\n"
                f"{clean_question}"
            )
        )
        
        response = await self._llm.generate(request)
        return response.text