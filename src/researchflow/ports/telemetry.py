from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal,Protocol,ContextManager

Scalar=str|int|float|bool


@dataclass(frozen=True)
class RuntimeFailure:
    kind: Literal['provider','protocol','retrieval','verification','persistence','budget','cancelled']
    run_id: str
    step_id: str
    error_class: str


class SpanHandle(Protocol):
    def set_attribute(self,key: str,value: Scalar) -> None: ...
    def add_event(self,name: str,attributes: dict[str,Scalar] | None = None) -> None: ...


class TracePort(Protocol):
    def span(self,name: str,attributes: dict[str,Scalar]) -> ContextManager[SpanHandle]: ...
    def record_failure(self,failure: RuntimeFailure) -> None: ...


class NullSpan:
    def set_attribute(self,key,value):
        pass
    def add_event(self,name,attributes=None):
        pass


class NullTrace:
    @contextmanager
    def span(self,name,attributes):
        yield NullSpan()
    def record_failure(self,failure):
        pass
    def close(self):
        pass
