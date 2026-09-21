from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class LLMRequest:
    prompt: str

@dataclass(frozen=True)
class LLMResponse:
    text: str

class LLMPort(Protocol):
    async def generate(self,request: LLMRequest)->LLMResponse:
        ...