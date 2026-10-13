import { useState } from 'react';
import { useMutation,useQueryClient } from '@tanstack/react-query';
import { Upload,Link as LinkIcon } from 'lucide-react';
import { api,SourceSnapshot,errorText } from '../lib/api';
import { keys } from '../lib/queryKeys';

export default function SourceUpload({projectId}:{projectId:string}) {
  const client=useQueryClient(),[url,setUrl]=useState(''),[localError,setLocalError]=useState('');
  const invalidate=()=>{void client.invalidateQueries({queryKey:keys.sources(projectId)});};
  const upload=useMutation({mutationFn:(file:File)=>api.upload<SourceSnapshot>('/api/projects/'+projectId+'/sources',file),onSuccess:invalidate});
  const fetchUrl=useMutation({mutationFn:()=>api.post<SourceSnapshot>('/api/projects/'+projectId+'/sources',{url}),onSuccess:()=>{setUrl('');invalidate();}});
  return <section className="upload-panel"><div className="upload-intro"><span className="source-icon"><Upload size={22}/></span><div><h3>把研究材料放在一起</h3><p>支持文字 PDF、TXT、Markdown 和 HTML，单个文件最多 20 MB。</p></div><label className="button" htmlFor="source-file">上传资料</label><input id="source-file" className="visually-hidden" aria-label="上传资料" type="file" accept=".pdf,.txt,.md,.html,.htm" onChange={event=>{const file=event.target.files?.[0];if(!file)return;if(file.size>20*1024*1024){setLocalError('文件超过 20 MB，请上传较小的文件。');return;}setLocalError('');upload.mutate(file);event.target.value='';}}/></div><form className="url-form" onSubmit={event=>{event.preventDefault();fetchUrl.mutate();}}><LinkIcon size={16}/><input aria-label="资料网址" type="url" value={url} onChange={event=>setUrl(event.target.value)} placeholder="也可以导入公开网页或论文 PDF 的网址" required/><button className="button small" disabled={fetchUrl.isPending}>导入网址</button></form>{(upload.isPending||fetchUrl.isPending)&&<p role="status" className="muted">正在保存资料并建立原文索引…</p>}{(localError||upload.error||fetchUrl.error)&&<p role="alert" className="notice error">{localError||errorText(upload.error||fetchUrl.error)}</p>}</section>;
}
