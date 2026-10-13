from langgraph.checkpoint.base import BaseCheckpointSaver,CheckpointTuple,WRITES_IDX_MAP
from researchflow.infrastructure.storage.checkpoint_repository import CheckpointRepository
from researchflow.runtime.checkpoint_serializer import JSONSerializer


class FencedCheckpointer(BaseCheckpointSaver):
    def __init__(self,database,runs,handle):
        super().__init__(serde=JSONSerializer())
        self.handle=handle
        self.repository=CheckpointRepository(database,runs,handle)

    def scope(self,config):
        values=config.get('configurable',{})
        if values.get('thread_id')!=self.handle.run_id:
            raise ValueError('checkpoint thread does not belong to this run')
        namespace=values.get('checkpoint_ns','')
        if not isinstance(namespace,str) or len(namespace)>500:
            raise ValueError('invalid checkpoint namespace')
        return namespace,values.get('checkpoint_id')

    def config_for(self,namespace,checkpoint_id):
        return {'configurable':{'thread_id':self.handle.run_id,'checkpoint_ns':namespace,'checkpoint_id':checkpoint_id}}

    async def aget_tuple(self,config):
        namespace,checkpoint_id=self.scope(config)
        row=await self.repository.get(namespace,checkpoint_id)
        if row is None:
            return None
        return CheckpointTuple(self.config_for(namespace,row['id']),self.serde.loads_typed(('json',row['checkpoint'].encode())),self.serde.loads_typed(('json',row['metadata'].encode())),self.config_for(namespace,row['parent_id']) if row['parent_id'] else None,[(task,channel,self.serde.loads_typed(('json',value.encode()))) for task,channel,value in row['writes']])

    async def aput(self,config,checkpoint,metadata,new_versions):
        namespace,parent_id=self.scope(config)
        _,body=self.serde.dumps_typed(checkpoint)
        _,meta=self.serde.dumps_typed(metadata)
        await self.repository.put_checkpoint(namespace,checkpoint['id'],parent_id,body.decode(),meta.decode())
        return self.config_for(namespace,checkpoint['id'])

    async def aput_writes(self,config,writes,task_id,task_path=''):
        namespace,checkpoint_id=self.scope(config)
        if not checkpoint_id:
            raise ValueError('pending writes require a saved checkpoint')
        rows=[(WRITES_IDX_MAP.get(channel,idx),channel,self.serde.dumps_typed(value)[1].decode()) for idx,(channel,value) in enumerate(writes)]
        await self.repository.put_writes(namespace,checkpoint_id,task_id,task_path,rows)

    async def alist(self,config,*,filter=None,before=None,limit=None):
        namespace,_=self.scope(config)
        before_id=self.scope(before)[1] if before else None
        for checkpoint_id in await self.repository.ids(namespace,before_id,limit):
            item=await self.aget_tuple(self.config_for(namespace,checkpoint_id))
            if item and (not filter or all(item.metadata.get(k)==v for k,v in filter.items())):
                yield item
