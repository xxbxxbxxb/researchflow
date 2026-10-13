import { useLocation,useNavigationType } from 'react-router-dom';
import { useEffect,useState,useLayoutEffect,useRef } from 'react';

export function useStickyState<T>(key:string,initial:T) {
  const [value,setValue]=useState<T>(()=>{
    try { const saved=sessionStorage.getItem(key); return saved?JSON.parse(saved) as T:initial; }
    catch { return initial; }
  });
  useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(value));}catch{/* current input remains usable */}},[key,value]);
  return [value,setValue] as const;
}

export function usePageScroll(ready:boolean) {
  const location=useLocation(),navigation=useNavigationType();
  const key='rf:scroll:'+location.pathname+':'+(new URLSearchParams(location.search).get('project_id')??'');
  const target=useRef(Number(sessionStorage.getItem(key)??'0'));
  const restored=useRef(false);
  useLayoutEffect(()=>{
    if(!ready||restored.current)return;
    restored.current=true;
    // Query data is now in the DOM; restoring while only a loading placeholder
    // exists would clamp the saved position to zero.
    window.scrollTo(0,navigation==='POP'&&Number.isFinite(target.current)?target.current:0);
  },[ready,key,navigation]);
  useEffect(()=>{
    if(!ready)return;
    const save=()=>{sessionStorage.setItem(key,String(window.scrollY));};
    window.addEventListener('scroll',save,{passive:true});
    const pageHide=()=>save();
    window.addEventListener('pagehide',pageHide);
    return ()=>{save();window.removeEventListener('scroll',save);window.removeEventListener('pagehide',pageHide);};
  },[ready,key]);
}
