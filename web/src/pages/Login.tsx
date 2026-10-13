import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { BookOpen,ArrowRight } from 'lucide-react';
import { api,Session,errorText } from '../lib/api';

export default function Login({onSuccess}:{onSuccess:(session:Session)=>void}) {
  const [password,setPassword]=useState('');
  const mutation=useMutation({mutationFn:()=>api.post<Session>('/api/auth/login',{password}),onSuccess});
  return <main className="login-shell"><section className="login-story"><div className="brand"><BookOpen size={26}/><span>ResearchFlow</span></div><p className="eyebrow">YOUR RESEARCH, WITH EVIDENCE</p><h1>每一个结论，<br/>都有迹可循。</h1><p>把资料、研究问题与证据串联起来。<br/>从原文出发，留下可以复核的研究记录。</p><div className="login-flow"><span>01 原始资料</span><span>02 证据核对</span><span>03 项目知识</span></div></section><section className="login-form"><p className="eyebrow">研究工作台</p><h2>欢迎回来</h2><p className="muted">使用你的工作台密码继续研究。</p><form onSubmit={event=>{event.preventDefault();mutation.mutate();}}><label>密码<input type="password" autoComplete="current-password" value={password} onChange={event=>setPassword(event.target.value)} required/></label>{mutation.error&&<p role="alert" className="notice error">{errorText(mutation.error)}</p>}<button className="button primary" disabled={mutation.isPending}>{mutation.isPending?'正在登录…':'进入工作台'}<ArrowRight size={17}/></button></form><p className="login-note">你的资料与研究记录保存在自己的工作台中。</p></section></main>;
}
