"""Closed, JSON-only checkpoint format. No dynamic type lookup or pickle."""
import json
import math
from langgraph.types import Interrupt


class JSONSerializer:
    def encode(self,value):
        if value is None or type(value) in (str,int,bool):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if isinstance(value,Interrupt):
            return {'t':'interrupt','v':self.encode(value.value),'id':value.id,'schema':self.encode(value.response_schema)}
        if type(value) in (tuple,list):
            return {'t':'tuple' if type(value) is tuple else 'list','v':[self.encode(v) for v in value]}
        if type(value) is dict and all(type(k) is str for k in value):
            return {'t':'dict','v':[[k,self.encode(v)] for k,v in value.items()]}
        raise ValueError('checkpoint supports only JSON values and the trusted Interrupt envelope')

    def decode(self,value):
        if type(value) is not dict:
            if value is None or type(value) in (str,int,bool) or type(value) is float and math.isfinite(value):
                return value
            raise ValueError('invalid JSON checkpoint scalar')
        tag=value.get('t')
        if tag in ('tuple','list') and set(value)=={'t','v'} and type(value['v']) is list:
            items=[self.decode(v) for v in value['v']]
            return tuple(items) if tag=='tuple' else items
        if tag=='dict' and set(value)=={'t','v'} and type(value['v']) is list:
            if any(type(pair) is not list or len(pair)!=2 or type(pair[0]) is not str for pair in value['v']):
                raise ValueError('invalid checkpoint mapping')
            return {k:self.decode(v) for k,v in value['v']}
        if tag=='interrupt' and set(value)=={'t','v','id','schema'} and type(value['id']) is str:
            schema=self.decode(value['schema'])
            if schema is not None and type(schema) is not dict:
                raise ValueError('interrupt schema must be JSON')
            return Interrupt(self.decode(value['v']),id=value['id'],response_schema=schema)
        raise ValueError('unknown checkpoint envelope')

    def dumps_typed(self,value):
        payload=json.dumps(self.encode(value),ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        if len(payload)>4*1024*1024:
            raise ValueError('checkpoint is too large')
        return 'json',payload

    def loads_typed(self,data):
        kind,payload=data
        if kind!='json' or len(payload)>4*1024*1024:
            raise ValueError('only bounded JSON checkpoints are accepted')
        return self.decode(json.loads(payload))
