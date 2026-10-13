import { useQuery } from '@tanstack/react-query';
import { X,ExternalLink,FileText } from 'lucide-react';
import { api,EvidenceBundle,scope,errorText } from '../lib/api';
import { useWorkspace } from '../context';

export default function EvidenceDrawer() {
  const {evidence:selection,closeEvidence}=useWorkspace();
  const detail=useQuery({queryKey:['evidence',selection?.projectId,selection?.evidenceId],queryFn:()=>api.get<EvidenceBundle>(scope('/api/evidence/'+selection!.evidenceId,selection!.projectId)),enabled:!!selection,staleTime:Infinity});
  if(!selection)return null;
  const evidence=detail.data?.evidence,snapshot=detail.data?.snapshot;
  const page=snapshot?.pages.find(page=>page.number===evidence?.anchor.page);
  return <aside className="evidence-drawer" data-testid="evidence-drawer" role="dialog" aria-modal="false" aria-labelledby="evidence-title"><header><div><p className="eyebrow">SOURCE EVIDENCE</p><h2 id="evidence-title">原文证据</h2></div><button className="icon-button" aria-label="关闭原文" onClick={closeEvidence}><X size={20}/></button></header>{detail.isPending&&<p className="muted">正在载入保存的原文…</p>}{detail.error&&<p role="alert" className="notice error">{errorText(detail.error)}</p>}{evidence&&snapshot&&<><div className="source-heading"><FileText size={18}/><div><strong>{evidence.evidence.source.replace(/^upload:/,'')}</strong><span>第 {evidence.anchor.page} 页 · 已保存原文</span></div></div><blockquote data-testid="evidence-quote">{evidence.evidence.text}</blockquote><div className="section-heading"><h3>原文上下文</h3><a href={'/api/projects/'+selection.projectId+'/sources/'+snapshot.snapshot_id+'/original'} className="text-link" target="_blank" rel="noreferrer">下载原始资料<ExternalLink size={13}/></a></div><div className="source-page">{page?.text.slice(0,evidence.anchor.start)}<mark>{page?.text.slice(evidence.anchor.start,evidence.anchor.end)}</mark>{page?.text.slice(evidence.anchor.end)}</div><details className="anchor-details"><summary>保存与定位信息</summary><dl><dt>保存时间</dt><dd>{new Date(snapshot.fetched_at).toLocaleString('zh-CN')}</dd><dt>内容指纹</dt><dd>{snapshot.content_hash}</dd><dt>引用范围</dt><dd>{evidence.anchor.start}–{evidence.anchor.end} 字符</dd></dl></details></>}</aside>;
}
