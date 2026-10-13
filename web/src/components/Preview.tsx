import { useState,useRef,useEffect } from 'react';
import { csrfToken,scope,errorText } from '../lib/api';

export default function Preview({runId,projectId}:{runId:string;projectId:string}) {
  const [text,setText]=useState(''),[status,setStatus]=useState('未开始');
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  async function start() {
    controller.current?.abort();
    const abort=new AbortController();controller.current=abort;
    setText('');setStatus('临时生成，尚未验证');
    try {
      const response=await fetch(scope('/api/runs/'+runId+'/preview',projectId),{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':decodeURIComponent(csrfToken())},signal:abort.signal});
      if(!response.ok||!response.body)throw new Error('预览暂不可用，请检查运行状态。');
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
      try {
        while(true) {
          const next=await reader.read();if(next.done)break;
          buffer+=decoder.decode(next.value,{stream:true});
          const frames=buffer.split('\n\n');buffer=frames.pop()??'';
          for(const frame of frames) {
            const data=frame.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');
            if(!data)continue;
            const event=JSON.parse(data);
            if(event.delta?.kind==='text')setText(current=>current+String(event.delta.text));
            if(event.status==='completed')setStatus('预览已结束，内容仍未验证');
            if(event.status==='incomplete')setStatus('预览不完整，请重新生成');
          }
        }
      } finally {reader.releaseLock();}
    } catch(error) {setStatus(abort.signal.aborted?'预览已停止，内容不完整':errorText(error));}
    finally {if(controller.current===abort)controller.current=null;}
  }
  return <section className="activity-panel"><h2>临时生成预览</h2><p className="notice">预览会使用本次研究的模型预算。内容尚未验证，正式结论请查看研究报告。</p><p role="status">{status}</p>{text&&<pre style={{whiteSpace:'pre-wrap'}}>{text}</pre>}<div className="action-row"><button className="button" onClick={()=>void start()}>生成预览</button><button className="button" disabled={!controller.current} onClick={()=>controller.current?.abort()}>停止预览</button></div></section>;
}
