import { useParams,useSearchParams,Link } from 'react-router-dom';
import { useQuery,useMutation,useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { Download,ArrowRight,FileCheck } from 'lucide-react';
import { api,ResearchResult,ReportVersion,Schema,scope,link,errorText,dateText } from '../lib/api';
import { keys } from '../lib/queryKeys';
import { useProjectLive } from '../lib/events';
import { useStickyState } from '../lib/state';
import { useWorkspace } from '../context';
import ClaimCard from '../components/ClaimCard';

export default function ReportPage() {
  const {id}=useParams(),[search]=useSearchParams(),projectId=search.get('project_id');
  return id&&projectId?<ReportContent key={id} reportId={id} projectId={projectId}/>:<p>从项目工作台打开研究报告。</p>;
}
function ReportContent({reportId,projectId}:{reportId:string;projectId:string}) {
  const {openEvidence}=useWorkspace(),client=useQueryClient();
  useProjectLive(projectId);
  const detail=useQuery({queryKey:keys.report(reportId),queryFn:()=>api.get<ResearchResult>(scope('/api/reports/'+reportId,projectId)),staleTime:Infinity});
  const versions=useQuery({queryKey:keys.reports(projectId),queryFn:()=>api.get<ReportVersion[]>('/api/projects/'+projectId+'/reports'),refetchInterval:1000});
  const result=detail.data,newer=versions.data?.find(version=>version.task_id===result?.task_id&&version.version>(result?.report.version??0));
  const [question,setQuestion]=useStickyState('rf:followup:'+reportId,'');
  const draft=useMutation({mutationFn:()=>api.post<Schema['FollowUpDraft']>('/api/projects/'+projectId+'/follow-ups',{parent_task_id:result!.task_id,question,claim_ids:result!.claims.map(claim=>claim.claim_id)}),onSuccess:()=>{setQuestion('');void client.invalidateQueries({queryKey:keys.drafts(projectId)});}});
  const download=()=>{if(!result)return;const url=URL.createObjectURL(new Blob([result.report.markdown],{type:'text/markdown;charset=utf-8'}));const element=document.createElement('a');element.href=url;element.download='research-report-v'+result.report.version+'.md';element.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  if(detail.error)return <p role="alert" className="notice error">{errorText(detail.error)}</p>;
  if(!result)return <p className="muted">正在载入研究报告…</p>;
  return <><Link className="breadcrumb" to={'/projects/'+projectId}>项目工作台 / 研究报告</Link><header className="page-heading"><div><p className="eyebrow">EVIDENCE-BASED REPORT</p><h1>研究报告</h1><p className="muted">版本 {result.report.version} · {dateText(result.report.created_at)}</p></div><button className="button" onClick={download}><Download size={16}/>导出报告</button></header><div className="report-meta"><span className={'badge '+(result.execution_mode==='demo'?'neutral':'supported')}>{result.execution_mode==='demo'?'固定演示':'真实模型'}</span><span>{result.claims.length} 条主张</span><span>{result.report.conclusion_claim_ids.length} 条得到材料支持</span><span>{result.report.retrieval_mode==='hybrid'?'混合检索':result.report.retrieval_mode==='lexical'?'词法检索':'人工材料'}</span></div>{result.execution_mode==='demo'&&<p className="notice">固定案例用于验证证据流程与交互，不代表真实模型质量。</p>}<div className="version-notice">{newer&&<Link className="notice text-link" to={link('reports',newer.report_id,projectId)}>有更新的报告<ArrowRight size={16}/></Link>}</div><article className="report-document"><ReactMarkdown components={{h1:({children})=><h2>{children}</h2>,a:({href,children,...props})=>{if(href?.startsWith('/api/evidence/')){const url=new URL(href,window.location.origin);const id=decodeURIComponent(url.pathname.split('/').pop()??'');return <button className="citation-link" onClick={()=>openEvidence(projectId,id)}>{children}</button>;}return <a href={href} {...props} rel="noreferrer">{children}</a>;}}}>{result.report.markdown}</ReactMarkdown></article><div className="section-heading"><div><p className="eyebrow">CLAIM BY CLAIM</p><h2>逐项证据核对</h2></div><FileCheck size={24}/></div>{result.claims.map(claim=>{const verification=result.verifications.find(item=>item.claim_id===claim.claim_id);return verification&&<ClaimCard key={claim.claim_id} claim={claim} verification={verification} evidences={result.evidences}/>;})}{!result.claims.length&&<section className="empty-state compact"><h3>当前材料不足以形成有依据的结论</h3><p>可以补充原始资料，或把尚未解决的问题保存为后续草稿。</p></section>}<section className="question-panel"><p className="eyebrow">KEEP EXPLORING</p><h2>把未解决的问题，留给下一次研究</h2><form onSubmit={event=>{event.preventDefault();draft.mutate();}}><label>后续研究问题<textarea value={question} onChange={event=>setQuestion(event.target.value)} required placeholder="还需要核对哪些条件，或者寻找哪类证据？"/></label><p className="muted">保存为草稿，不会自动调用模型。你可以在项目知识中启动。</p><button className="button primary" disabled={draft.isPending||!question.trim()||Array.from(question).length>5000}>保存后续草稿<ArrowRight size={17}/></button>{draft.isSuccess&&<p role="status" className="notice success">后续草稿已保存</p>}{draft.error&&<p role="alert" className="notice error">{errorText(draft.error)}</p>}</form></section><div className="action-row"><Link className="text-link" to={'/projects/'+projectId+'?tab=knowledge'}>查看项目知识与后续草稿 →</Link><Link className="text-link" to={link('runs',result.run_id,projectId)}>查看本次运行记录</Link></div></>;
}
