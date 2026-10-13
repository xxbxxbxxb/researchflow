import math
from dataclasses import dataclass, field, replace
from typing import Literal


class BudgetExceededError(RuntimeError):
    def __init__(self, message: str, resource: str = 'model') -> None:
        super().__init__(message)
        self.resource = resource


@dataclass(frozen=True,slots=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    price_version: str | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens,self.output_tokens):
            if value is not None and (type(value) is not int or value<0):
                raise ValueError('usage tokens must be nonnegative integers or unknown')
        if self.estimated_cost is not None and (isinstance(self.estimated_cost,bool) or not math.isfinite(self.estimated_cost) or self.estimated_cost<0 or not self.price_version):
            raise ValueError('estimated cost requires finite nonnegative value and a price version')


@dataclass(frozen=True,slots=True)
class RunLimits:
    max_steps: int = 12
    max_tool_calls: int = 20
    max_model_calls: int = 16
    max_concurrency: int = 4
    active_timeout_seconds: float = 300.0
    operation_timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        for name,ceiling in (('max_steps',12),('max_tool_calls',20),('max_model_calls',16),('max_concurrency',4)):
            value=getattr(self,name)
            if type(value) is not int or not 1<=value<=ceiling:
                raise ValueError('run limit must be a positive bounded integer')
        for name,ceiling in (('active_timeout_seconds',300),('operation_timeout_seconds',60)):
            value=getattr(self,name)
            if isinstance(value,bool) or not math.isfinite(value) or not 0<value<=ceiling:
                raise ValueError('run timeout must be finite and within its ceiling')


@dataclass(frozen=True,slots=True)
class RunBudget:
    model_calls_used: int = 0
    tool_calls_used: int = 0
    steps_used: int = 0
    active_elapsed_seconds: float = 0.0
    limits: RunLimits = field(default_factory=RunLimits)

    def reserve(self, resource: Literal['model','tool','step'], amount: int = 1) -> 'RunBudget':
        if type(amount) is not int or amount<1:
            raise ValueError('reservation amount must be a positive integer')
        fields={'model':('model_calls_used','max_model_calls'),'tool':('tool_calls_used','max_tool_calls'),'step':('steps_used','max_steps')}
        if resource not in fields:
            raise ValueError('unknown budget resource')
        used,maximum=fields[resource]
        value=getattr(self,used)+amount
        if value>getattr(self.limits,maximum):
            raise BudgetExceededError(resource+' budget exhausted',resource)
        return replace(self,**{used:value})

    def charge(self, seconds: float) -> 'RunBudget':
        if not math.isfinite(seconds) or seconds<0:
            raise ValueError('elapsed time must be finite and nonnegative')
        value=self.active_elapsed_seconds+seconds
        if value>=self.limits.active_timeout_seconds:
            raise BudgetExceededError('active run deadline exhausted','active')
        return replace(self,active_elapsed_seconds=value)
