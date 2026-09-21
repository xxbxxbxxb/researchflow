import asyncio

from researchflow.application.use_cases.ask_research_question import(
    AskResearchQuestion,
)
from researchflow.infrastructure.llm.fake_llm import FakeLLM

async def main() ->None:
    llm = FakeLLM(
        response_text=(
            "SSE is suitable for server-to-client event streaming "
            "when bidirectional communication is not required."
        )
    )
    
    use_case = AskResearchQuestion(llm)
    
    answer =  await use_case.execute(
        (
            "When is SSE more suitable than WebSocket?"
        )
        
    )
    print("ResearchFlow Day 1")
    print("------------------")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())