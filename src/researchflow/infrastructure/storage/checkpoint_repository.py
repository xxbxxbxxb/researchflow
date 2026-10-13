from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from researchflow.infrastructure.storage.models import CheckpointRow, GraphWriteRow
from researchflow.ports.runtime import InputVersionMismatchError


class CheckpointRepository:
    def __init__(self,database,runs,handle):
        self.database,self.runs,self.handle=database,runs,handle

    def filters(self,namespace):
        return (CheckpointRow.project_id==self.handle.project_id,CheckpointRow.run_id==self.handle.run_id,CheckpointRow.namespace==namespace)

    async def get(self,namespace,checkpoint_id=None):
        async with self.database.session.begin() as session:
            run=await self.runs.fence(session,self.handle)
            query=select(CheckpointRow).where(*self.filters(namespace)).order_by(CheckpointRow.checkpoint_id.desc()).limit(1)
            if checkpoint_id:
                query=query.where(CheckpointRow.checkpoint_id==checkpoint_id)
            row=(await session.scalars(query)).one_or_none()
            if row is None:
                return None
            if row.input_version != run.input_version:
                raise InputVersionMismatchError('checkpoint input policy is incompatible')
            writes=(await session.scalars(select(GraphWriteRow).where(GraphWriteRow.project_id==self.handle.project_id,GraphWriteRow.run_id==self.handle.run_id,GraphWriteRow.namespace==namespace,GraphWriteRow.checkpoint_id==row.checkpoint_id).order_by(GraphWriteRow.task_path,GraphWriteRow.task_id,GraphWriteRow.idx))).all()
            return {'id':row.checkpoint_id,'parent_id':row.parent_id,'checkpoint':row.checkpoint_data,'metadata':row.metadata_data,'writes':[(w.task_id,w.channel,w.value_data) for w in writes]}

    async def put_checkpoint(self,namespace,checkpoint_id,parent_id,checkpoint,metadata):
        async with self.database.session.begin() as session:
            run=await self.runs.fence(session,self.handle)
            values={'project_id':self.handle.project_id,'run_id':self.handle.run_id,'namespace':namespace,'checkpoint_id':checkpoint_id,'parent_id':parent_id,'input_version':run.input_version,'checkpoint_data':checkpoint,'metadata_data':metadata}
            await session.execute(insert(CheckpointRow).values(**values).on_conflict_do_nothing())
            await self.runs.fence(session,self.handle)

    async def put_writes(self,namespace,checkpoint_id,task_id,task_path,writes):
        async with self.database.session.begin() as session:
            await self.runs.fence(session,self.handle)
            for idx,channel,value in writes:
                values={'project_id':self.handle.project_id,'run_id':self.handle.run_id,'namespace':namespace,'checkpoint_id':checkpoint_id,'task_id':task_id,'task_path':task_path,'idx':idx,'channel':channel,'value_data':value}
                statement=insert(GraphWriteRow).values(**values)
                if idx<0:
                    statement=statement.on_conflict_do_update(index_elements=['project_id','run_id','namespace','checkpoint_id','task_id','idx'],set_={'value_data':value,'channel':channel})
                else:
                    statement=statement.on_conflict_do_nothing()
                await session.execute(statement)
            await self.runs.fence(session,self.handle)

    async def ids(self,namespace,before=None,limit=100):
        async with self.database.session.begin() as session:
            await self.runs.fence(session,self.handle)
            query=select(CheckpointRow.checkpoint_id).where(*self.filters(namespace)).order_by(CheckpointRow.checkpoint_id.desc()).limit(min(limit or 100,1000))
            if before:
                query=query.where(CheckpointRow.checkpoint_id<before)
            return tuple((await session.scalars(query)).all())
