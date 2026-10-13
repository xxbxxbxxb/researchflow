from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langgraph.types import interrupt,Command

from researchflow.domain.runs import RunOutcome
from researchflow.runtime.fixed_workflow import FixedWorkflow,PHASES
from researchflow.runtime.checkpointer import FencedCheckpointer


class GraphState(TypedDict,total=False):
    run_id: str
    report_id: str
    phase: str


class GraphWorkflow(FixedWorkflow):
    workflow_version='graph-v1'

    async def execute(self,handle,review_decision=None):
        record,_=await self.inputs(handle)
        repository=getattr(self.runs,'repository',self.runs)
        saver=FencedCheckpointer(repository.database,repository,handle)
        builder=StateGraph(GraphState)
        for phase in PHASES:
            async def node(state,phase=phase):
                output=await self.step(handle,phase)
                data={'phase':phase}
                if output.result:
                    data['report_id']=output.result.report.report_id
                return data
            builder.add_node(phase,node)
        def review(state):
            if record.input_manifest.get('require_review'):
                answer=interrupt({'report_id':state['report_id'],'action':'review'})
                if not isinstance(answer,dict) or answer.get('action')!='approve':
                    raise ValueError('an approved durable review decision is required')
            return {'phase':'reviewed'}
        builder.add_node('review',review)
        builder.add_edge(START,PHASES[0])
        for before,after in zip(PHASES,PHASES[1:]):
            builder.add_edge(before,after)
        builder.add_edge('report','review')
        builder.add_edge('review',END)
        graph=builder.compile(checkpointer=saver)
        config={'configurable':{'thread_id':handle.run_id,'checkpoint_ns':''}}
        saved=await saver.aget_tuple(config)
        decision=await repository.get_review(handle.project_id,handle.run_id)
        value=Command(resume={'action':decision.action}) if decision else None if saved else {'run_id':handle.run_id}
        result=await graph.ainvoke(value,config)
        return RunOutcome('awaiting_review' if result.get('__interrupt__') else 'succeeded',result.get('report_id'))
