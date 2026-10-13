import hashlib

from researchflow.ports.telemetry import Scalar

SAFE={'run_id','task_id','project_id','step_id','attempt_id','epoch','operation','model','status','failure_kind','error_class','latency_seconds','execution_mode','tool_name'}


def redact(attributes: dict[str,Scalar]) -> dict[str,Scalar]:
    result={}
    for key,value in attributes.items():
        if any(s in key.lower() for s in ('key','token','password','authorization','cookie','secret')):
            continue
        if key in SAFE and type(value) in (str,int,float,bool):
            result[key]=value[:200] if isinstance(value,str) else value
        else:
            encoded=str(value).encode()
            result[key+'.length']=len(encoded)
            result[key+'.sha256']=hashlib.sha256(encoded).hexdigest()
    return result
