import { useRef } from 'react';
import { useParams,useSearchParams,Link,useNavigate } from 'react-router-dom';
import { useQuery,useMutation } from '@tanstack/react-query';
import { ArrowRight } from 'lucide-react';
import { api,TaskRecord,RunRecord,Schema,link,errorText } from '../lib/api';
import { keys } from '../lib/queryKeys';
import { useProjectLive } from '../lib/events';
import { useStickyState } from '../lib/state';
import { useWorkspace } from '../context';
import RunProgress from '../components/RunProgress';

export default function TaskPage() {
  const {id}=useParams(),[search]=useSearchParams(),projectId=search.get('project_id');
  return id&&projectId?<TaskContent key={id} taskId={id} projectId={projectId}/>:<p>从项目工作台打开研究任务。</p>;
}
function TaskContent({taskId,projectId}:{taskId:string;projectId:string}) {
  const {session}=useWorkspace(),navigate=useNavigate(),starting=useRef(false);
  const tasks=useQuery({queryKey:keys.tasks(projectId),queryFn:()=>api.get<TaskRecord[]>('/api/projects/'+projectId+'/tasks')});
  const task=tasks.data?.find(task=>task.task_id===taskId),runs=useProjectLive(projectId);
  const latest=runs.data?.find(run=>run.task_id===taskId);
  const [mode,setMode]=useStickyState<'demo'|'live'>('rf:task-mode:'+taskId,session.execution_mode);
  const [demoCase,setDemoCase]=useStickyState<Schema['RunStart']['demo_case']>('rf:task-case:'+taskId,'supported');
  const [collect,setCollect]=useStickyState('rf:task-collect:'+taskId,false);
  const [review,setReview]=useStickyState('rf:task-review:'+taskId,false);
  const start=useMutation({mutationFn:(key:string)=>api.post<RunRecord>('/api/tasks/'+taskId+'/runs',{project_id:projectId,mode,demo_case:demoCase,driver:'graph',require_review:review,collect_sources:mode==='live'&&collect},key),onSuccess:run=>navigate(link('runs',run.run_id,projectId)),onSettled:()=>{starting.current=false;}});
  const begin=(repeat=false)=>{if(starting.current)return;starting.current=true;start.mutate(repeat?'repeat:'+taskId+':'+crypto.randomUUID():'start:'+taskId);};
  return <><Link className="breadcrumb" to={'/projects/'+projectId+'?tab=tasks'}>项目工作台 / 研究任务</Link><header className="page-heading"><div><p className="eyebrow">RESEARCH QUESTION</p><h1 className="question-title">{task?.question??'研究任务'}</h1><p className="muted">{task?.source_ids.length??0} 份指定资料 · 保存输入版本后启动</p></div></header>{task?.parent_task_id&&<p className="notice">这是一个后续研究任务。<Link className="text-link" to={link('tasks',task.parent_task_id,projectId)}>查看原研究 →</Link></p>}{latest?<><RunProgress run={latest}/>{['succeeded','failed','cancelled'].includes(latest.state)&&<button className="button" disabled={start.isPending} onClick={()=>begin(true)}>创建新运行，重新研究</button>}</>:<section className="start-panel"><h2>准备好开始了吗？</h2><p className="muted">系统会从保存的资料出发，提取主张、核对证据，并形成可复核的报告。</p><div className="form-options"><label>研究方式<select value={mode} onChange={event=>setMode(event.target.value as 'demo'|'live')}><option value="demo">固定演示</option><option value="live">真实模型</option></select></label>{mode==='demo'&&<label>固定演示案例<select value={demoCase} onChange={event=>setDemoCase(event.target.value as Schema['RunStart']['demo_case'])}><option value="supported">材料支持</option><option value="contradicted">相反证据</option><option value="insufficient">材料不足</option><option value="invalid-citation">非法引用被阻止</option></select></label>}</div><label className="checkbox-label"><input type="checkbox" checked={review} onChange={event=>setReview(event.target.checked)}/>完成报告后等待人工审阅</label>{mode==='live'&&<label className="checkbox-label"><input type="checkbox" checked={collect} onChange={event=>setCollect(event.target.checked)}/>允许检索并补充公开科研资料（使用同一运行预算）</label>}{mode==='demo'&&<p className="notice">固定案例用于验证流程，不代表真实模型效果。</p>}<button className="button primary" disabled={start.isPending||!task||runs.isPending} onClick={()=>begin()}>{start.isPending?'正在启动…':'开始研究'}<ArrowRight size={17}/></button></section>}{(start.error||tasks.error||runs.error)&&<p role="alert" className="notice error">{errorText(start.error||tasks.error||runs.error)}</p>}</>;
}
