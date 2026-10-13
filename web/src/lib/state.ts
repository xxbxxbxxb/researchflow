import { useEffect,useState } from 'react';

export function useStickyState<T>(key:string,initial:T) {
  const [value,setValue]=useState<T>(()=>{
    try { const saved=sessionStorage.getItem(key); return saved?JSON.parse(saved) as T:initial; }
    catch { return initial; }
  });
  useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(value));}catch{/* current input remains usable */}},[key,value]);
  return [value,setValue] as const;
}
