import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Check,Circle,Loader2,ArrowUpRight } from 'lucide-react';
import { api,RunRecord,RunEvent,ReportVersion,scope,link,errorText } from '../lib/api';
import { keys } from '../lib/queryKeys';

export const runLabels:Record<RunRecord['state'],string>={queued:'等待开始',running:'正在研究',awaiting_review:'等待人工审阅',succeeded:'研究已完成',failed:'研究未能完成',cancelled:'已取消',interrupted:'运行已中断'};
const phases=[['collect','整理资料'],['retrieve','检索相关段落'],['evidence','定位原文证据'],['claims','提取研究主张'],['verify','核对证据关系'],['report','形成研究报告']];
export default function RunProgress({run}:{run:RunRecord}) {
  const client=useQueryClient();
  const events=useQuery({queryKey:keys.events(run.run_id),queryFn:async()=>{
    const loaded=await api.get<RunEvent[]>(scope('/api/runs/'+run.run_id+'/event-history',run.project_id));
    const previous=client.getQueryData<RunEvent[]>(keys.events(run.run_id))??[];
    return [...new Map([...loaded,...previous].map(event=>[event.event_id,event])).values()].sort((a,b)=>a.event_id-b.event_id);
  }});
  const reports=useQuery({queryKey:keys.reports(run.project_id),queryFn:()=>api.get<ReportVersion[]>('/api/projects/'+run.project_id+'/reports'),refetchInterval:['queued','running'].includes(run.state)?1000:false});
  const completed=new Set(events.data?.filter(event=>event.kind==='step_committed').map(event=>event.data.step_key));
  const latest=reports.data?.find(report=>report.run_id===run.run_id);
  const action=useMutation({mutationFn:(operation:'cancel'|'resume'|'approve'|'reject')=>api.post<RunRecord>(scope('/api/runs/'+run.run_id+'/'+(['approve','reject'].includes(operation)?'review':operation),run.project_id),['approve','reject'].includes(operation)?{action:operation,comment:'已在工作台查看研究结果。'}:{}),onSuccess:()=>{void client.invalidateQueries({queryKey:keys.runs(run.project_id)});void client.invalidateQueries({queryKey:keys.run(run.run_id)});}});
  return <section className={'progress-panel state-'+run.state}><div className="section-heading"><div><p className="small-label">研究进度</p><h2>{runLabels[run.state]}</h2></div><span className={'badge '+(run.state==='succeeded'?'supported':run.state==='failed'?'contradicted':'neutral')}>{run.input_manifest.execution_mode==='demo'?'固定演示':'真实模型'}</span></div><ol className="phase-list">{phases.map(([key,label],index)=><li key={key} className={completed.has(key)||run.state==='succeeded'?'complete':''}><span className="phase-icon">{completed.has(key)||run.state==='succeeded'?<Check size={14}/>:run.state==='running'&&completed.size===index?<Loader2 size={14} className="spin"/>:<Circle size={12}/>}</span><span>{label}</span></li>)}</ol>{run.state==='failed'&&<p role="alert" className="notice error">本次研究未通过执行或引用校验，没有可交付的研究报告。请检查资料与模型配置后创建新运行。</p>}{run.cancel_requested&&run.state==='running'&&<p className="notice">取消请求已提交，正在结束当前操作。</p>}<div className="action-row">{latest&&<Link className="button primary" to={link('reports',latest.report_id,run.project_id)}>查看报告<ArrowUpRight size={16}/></Link>}{['queued','running'].includes(run.state)&&<button className="button danger" disabled={action.isPending||run.cancel_requested} onClick={()=>action.mutate('cancel')}>取消研究</button>}{run.state==='interrupted'&&<button className="button" disabled={action.isPending} onClick={()=>action.mutate('resume')}>恢复研究</button>}{run.state==='awaiting_review'&&<><button className="button primary" disabled={action.isPending} onClick={()=>action.mutate('approve')}>确认审阅并继续</button><button className="button" disabled={action.isPending} onClick={()=>action.mutate('reject')}>结束研究</button></>}<Link className="text-link" to={link('runs',run.run_id,run.project_id)}>运行记录 →</Link></div>{action.error&&<p role="alert" className="notice error">{errorText(action.error)}</p>}</section>;
}
