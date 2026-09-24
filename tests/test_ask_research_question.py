import asyncio
import pytest

from researchflow.application.use_cases.ask_research_question import(
    AskResearchQuestion,
)
from researchflow.infrastructure.llm.fake_llm import FakeLLM

def test_ask_research_question_returns_fake_llm_response() ->None:
    llm =FakeLLM(response_text="fake answer")
    use_case = AskResearchQuestion(llm)
    result = asyncio.run(
        use_case.execute("what is evidence grounding?")
    )
    
    assert result == "fake answer"
    assert llm.last_request is not None
    assert (
        "what is evidence grounding?"
        in llm.last_request.prompt
    )
    
def test_ask_research_question_rejects_blank_question() -> None:
    llm = FakeLLM(response_text="unused")
    use_case = AskResearchQuestion(llm)
    
    with pytest.raises(
        ValueError,
        match="question must not be empty",
    ):
        asyncio.run(
            use_case.execute("  ")
        )
    assert llm.last_request is None
def test_ask_research_question_rejects_too_long_question() -> None:
    llm = FakeLLM(response_text="unused")
    use_case = AskResearchQuestion(llm)
    
    with pytest.raises(
        ValueError,
        match="question must not exceed 5000 characters",
    ):
        asyncio.run(
            use_case.execute("1"*5001)
        )
    assert llm.last_request is None
def test_ask_research_question_accepts_normal_question() -> None:
    llm = FakeLLM(response_text="unused")
    use_case = AskResearchQuestion(llm)
    
    
    result =  asyncio.run(
            use_case.execute("1"*5000)
        )
    assert result == "unused"