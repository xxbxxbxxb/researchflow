import { useEffect } from 'react';
import { createBrowserRouter,RouterProvider,Outlet,NavLink,Link,Navigate,ScrollRestoration } from 'react-router-dom';
import { QueryClient,QueryClientProvider,useQuery,useQueryClient,useMutation } from '@tanstack/react-query';
import { BookOpen,Folder,LogOut,ArrowUpRight } from 'lucide-react';
import { api,Session,Project } from './lib/api';
import { keys } from './lib/queryKeys';
import { WorkspaceProvider } from './context';
import Login from './pages/Login';
import Projects from './pages/Projects';
import ProjectPage from './pages/Project';
import TaskPage from './pages/Task';
import ReportPage from './pages/Report';
import RunPage from './pages/Run';
import EvidenceDrawer from './components/EvidenceDrawer';
import './styles.css';

const client=new QueryClient({defaultOptions:{queries:{retry:1,refetchOnWindowFocus:false,staleTime:1000}}});
function Shell() {
  const queryClient=useQueryClient();
  const session=useQuery({queryKey:keys.session,queryFn:()=>api.get<Session>('/api/auth/session'),retry:false,staleTime:60000});
  useEffect(()=>{
    const unauthorized=()=>{queryClient.setQueryData(keys.session,null);void queryClient.invalidateQueries({queryKey:keys.session});};
    window.addEventListener('rf:unauthorized',unauthorized);
    return ()=>window.removeEventListener('rf:unauthorized',unauthorized);
  },[queryClient]);
  if(session.isPending)return <div className="loading-screen"><BookOpen size={30}/><span>正在打开研究工作台…</span></div>;
  if(session.error||!session.data)return <Login onSuccess={value=>queryClient.setQueryData(keys.session,value)}/>;
  return <WorkspaceProvider session={session.data}><WorkspaceFrame session={session.data}/></WorkspaceProvider>;
}
function WorkspaceFrame({session}:{session:Session}) {
  const client=useQueryClient();
  const projects=useQuery({queryKey:keys.projects,queryFn:()=>api.get<Project[]>('/api/projects')});
  const logout=useMutation({mutationFn:()=>api.post('/api/auth/logout',{}),onSuccess:()=>{client.clear();}});
  return <div className="app-shell"><aside className="sidebar"><Link to="/projects" className="brand"><BookOpen size={24}/><span>ResearchFlow</span></Link><div className="workspace-label">个人研究空间</div><nav className="side-nav"><NavLink to="/projects"><Folder size={18}/><span>研究项目</span></NavLink></nav><div className="sidebar-projects"><p className="small-label">项目列表</p>{projects.data?.slice(0,6).map(project=><Link key={project.project_id} to={'/projects/'+project.project_id}><span className="project-dot"/>{project.name}</Link>)}</div><div className="sidebar-bottom"><div className="sidebar-tip"><span>RESEARCH, WITH CARE</span><p>从一个问题开始，<br/>保留每一份依据。</p></div><a href="https://github.com/xxbxxbxxb/researchflow/tree/reference/mature-v1/docs" target="_blank" rel="noreferrer">使用说明<ArrowUpRight size={14}/></a></div></aside><header className="topbar"><span>研究工作台 <span className="topbar-divider">/</span><span className="muted">资料 · 证据 · 知识</span></span><div><span className="mode-pill">{session.execution_mode==='demo'?'固定演示':'真实模型'}</span><button className="icon-button" aria-label="退出登录" onClick={()=>logout.mutate()} disabled={logout.isPending}><LogOut size={17}/></button></div></header><main className="workspace-main"><Outlet/><footer className="workspace-footer"><span>ResearchFlow</span><span>资料可追溯，判断可审阅。</span></footer></main><EvidenceDrawer/><ScrollRestoration getKey={location=>location.pathname+new URLSearchParams(location.search).get('project_id')}/></div>;
}
const router=createBrowserRouter([{element:<Shell/>,children:[
  {index:true,element:<Navigate to="/projects" replace/>},
  {path:'/projects',element:<Projects/>},{path:'/projects/:id',element:<ProjectPage/>},
  {path:'/tasks/:id',element:<TaskPage/>},{path:'/reports/:id',element:<ReportPage/>},{path:'/runs/:id',element:<RunPage/>},
  {path:'*',element:<div className="empty-state"><h1>页面没有找到</h1><Link className="button" to="/projects">返回研究项目</Link></div>}
]}]);
export default function App(){return <QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>;}
