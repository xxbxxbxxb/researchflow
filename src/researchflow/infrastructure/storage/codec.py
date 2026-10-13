from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any


def jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value,type):
        return {f.name:jsonable(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,datetime):
        return value.isoformat()
    if isinstance(value,dict):
        return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [jsonable(v) for v in value]
    return value
