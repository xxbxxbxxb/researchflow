import math
import types
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints


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


def decode_dataclass(cls: Any, data: Any) -> Any:
    """Rebuild only a caller-selected trusted dataclass; no type names/pickle."""
    if cls is Any:
        return data
    origin,args = get_origin(cls),get_args(cls)
    if origin in (Union,types.UnionType):
        for option in args:
            try:
                return decode_dataclass(option,data)
            except (ValueError,TypeError):
                pass
        raise ValueError('stored value violates union type')
    if cls is type(None):
        if data is not None:
            raise ValueError('expected null')
        return None
    if origin is Literal:
        if data not in args:
            raise ValueError('stored literal invalid')
        return data
    if origin in (tuple,list):
        if not isinstance(data,(list,tuple)):
            raise ValueError('stored collection invalid')
        values = [decode_dataclass(args[0] if args else Any,v) for v in data]
        return tuple(values) if origin is tuple else values
    if origin is dict:
        if not isinstance(data,dict):
            raise ValueError('stored mapping invalid')
        return {k:decode_dataclass(args[1] if args else Any,v) for k,v in data.items()}
    if cls is datetime:
        return datetime.fromisoformat(data) if isinstance(data,str) else data
    if is_dataclass(cls):
        if not isinstance(data,dict):
            raise ValueError('stored record invalid')
        hints = get_type_hints(cls)
        return cast(Any,cls)(**{f.name:decode_dataclass(hints[f.name],data[f.name]) for f in fields(cls) if f.name in data})
    if cls is float:
        if type(data) not in (int,float) or not math.isfinite(data):
            raise ValueError('stored floating scalar invalid')
        return float(data)
    if cls in (str,int,bool):
        if not isinstance(data,cls) or cls is int and isinstance(data,bool):
            raise ValueError('stored scalar invalid')
        return data
    raise ValueError('unsupported stored type')
