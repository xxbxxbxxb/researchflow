import { useEffect } from 'react';
import { useQuery,useQueryClient } from '@tanstack/react-query';
import { api,RunEvent,RunRecord } from './api';
import { keys } from './queryKeys';

async function subscribe(projectId:string,runId:string,signal:AbortSignal,onEvent:(event:RunEvent)=>void) {
  const storageKey='rf:cursor:'+runId;
  let cursor=Number(sessionStorage.getItem(storageKey)??'0');
  while(!signal.aborted) {
    let terminal=false;
    try {
      const response=await fetch('/api/runs/'+encodeURIComponent(runId)+'/events?project_id='+encodeURIComponent(projectId),{signal,credentials:'same-origin',headers:{'Last-Event-ID':String(cursor)}});
      if(response.status===401){window.dispatchEvent(new Event('rf:unauthorized'));return;}
      if(!response.ok||!response.body)throw new Error('Progress subscription failed');
      const reader=response.body.getReader(),decoder=new TextDecoder();
      let buffer='';
      try {
        while(true) {
          const {value,done}=await reader.read(); if(done)break;
          buffer+=decoder.decode(value,{stream:true});
          let boundary:number;
          while((boundary=buffer.indexOf('\n\n'))>=0) {
            const frame=buffer.slice(0,boundary); buffer=buffer.slice(boundary+2);
            const data=frame.split('\n').filter(line=>line.startsWith('data: ')).map(line=>line.slice(6)).join('\n');
            if(!data)continue;
            const event=JSON.parse(data) as RunEvent;
            if(event.event_id<=cursor)continue;
            cursor=event.event_id; sessionStorage.setItem(storageKey,String(cursor)); onEvent(event);
            if(['succeeded','failed','cancelled'].includes(event.kind))terminal=true;
          }
        }
      }finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
    }catch{if(signal.aborted)return;}
    if(terminal)return;
    await new Promise<void>(resolve=>{
      const finish=()=>{clearTimeout(timer);signal.removeEventListener('abort',finish);resolve();};
      const timer=setTimeout(finish,1000);signal.addEventListener('abort',finish,{once:true});
    });
  }
}
export function useProjectLive(projectId:string) {
  const client=useQueryClient();
  const runs=useQuery({queryKey:keys.runs(projectId),queryFn:()=>api.get<RunRecord[]>('/api/projects/'+projectId+'/runs'),refetchInterval:1000});
  const ids=runs.data?.slice(0,3).map(run=>run.run_id).join(',')??'';
  useEffect(()=>{
    if(!ids)return;
    const controllers=ids.split(',').map(runId=>{
      const controller=new AbortController();
      void subscribe(projectId,runId,controller.signal,event=>{
        client.setQueryData<RunEvent[]>(keys.events(runId),old=>[...(old??[]).filter(e=>e.event_id!==event.event_id),event].slice(-200));
        void client.invalidateQueries({queryKey:keys.run(runId)});
        void client.invalidateQueries({queryKey:keys.runs(projectId)});
        void client.invalidateQueries({queryKey:keys.reports(projectId)});
      });
      return controller;
    });
    return ()=>controllers.forEach(controller=>controller.abort());
  },[client,projectId,ids]);
  return runs;
}
