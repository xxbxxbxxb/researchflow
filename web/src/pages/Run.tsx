import { useParams,useSearchParams,Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api,RunRecord,RunEvent,scope,link,errorText,dateText } from '../lib/api';
import { keys } from '../lib/queryKeys';
import { useProjectLive } from '../lib/events';
import RunProgress from '../components/RunProgress';
import Preview from '../components/Preview';
import { useWorkspace } from '../context';

export default function RunPage() {
  const {id}=useParams(),[search]=useSearchParams(),projectId=search.get('project_id');
  return id&&projectId?<RunContent key={id} runId={id} projectId={projectId}/>:<p>从项目工作台打开运行记录。</p>;
}
function RunContent({runId,projectId}:{runId:string;projectId:string}) {
  const {session}=useWorkspace();
  useProjectLive(projectId);
  const run=useQuery({queryKey:keys.run(runId),queryFn:()=>api.get<RunRecord>(scope('/api/runs/'+runId,projectId)),refetchInterval:1000});
  const events=useQuery({queryKey:keys.events(runId),queryFn:()=>api.get<RunEvent[]>(scope('/api/runs/'+runId+'/event-history',projectId)),refetchInterval:1000});
  const labels:Record<string,string>={queued:'已加入研究队列',claimed:'开始处理',step_committed:'研究阶段已保存',succeeded:'报告已完成',failed:'研究未完成',cancel_requested:'已收到取消请求',cancelled:'研究已取消',interrupted:'运行已中断',resumed:'恢复已排队',reviewed:'人工审阅已保存'};
  const phaseLabels:Record<string,string>={collect:'整理资料',retrieve:'检索相关段落',evidence:'定位原文证据',claims:'提取研究主张',verify:'核对证据关系',report:'形成研究报告'};
  return <><Link className="breadcrumb" to={'/projects/'+projectId+'?tab=tasks'}>项目工作台 / 运行记录</Link><header className="page-heading"><div><p className="eyebrow">RESEARCH ACTIVITY</p><h1>研究运行</h1><p className="muted">查看每个阶段的结果与保存记录。</p></div>{run.data&&<Link className="button" to={link('tasks',run.data.task_id,projectId)}>查看任务</Link>}</header>{run.data&&<RunProgress run={run.data}/>} {session.preview_enabled&&run.data?.state==='running'&&<Preview runId={runId} projectId={projectId}/>}<section className="activity-panel"><div className="section-heading"><h2>运行时间线</h2><span className="small-label">断开页面不会取消研究</span></div><ol className="timeline">{events.data?.map(event=><li key={event.event_id}><span className="timeline-dot"/><div><strong>{labels[event.kind]??event.kind}</strong>{typeof event.data.step_key==='string'&&<p>{phaseLabels[event.data.step_key]??event.data.step_key}</p>}<time>{dateText(event.created_at)}</time></div></li>)}</ol></section>{(run.error||events.error)&&<p role="alert" className="notice error">{errorText(run.error||events.error)}</p>}</>;
}
