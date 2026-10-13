from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    price_version: str | None = None
