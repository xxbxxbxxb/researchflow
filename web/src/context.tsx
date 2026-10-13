import { createContext,useContext,ReactNode } from 'react';
import { Session } from './lib/api';
import { useStickyState } from './lib/state';

type Selection={projectId:string;evidenceId:string}|null;
type Context={session:Session;evidence:Selection;openEvidence:(projectId:string,evidenceId:string)=>void;closeEvidence:()=>void};
const WorkspaceContext=createContext<Context|null>(null);
export function WorkspaceProvider({session,children}:{session:Session;children:ReactNode}) {
  const [evidence,setEvidence]=useStickyState<Selection>('rf:evidence',null);
  return <WorkspaceContext.Provider value={{session,evidence,openEvidence:(projectId,evidenceId)=>setEvidence({projectId,evidenceId}),closeEvidence:()=>setEvidence(null)}}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace(){const context=useContext(WorkspaceContext);if(!context)throw new Error('Workspace context unavailable');return context;}
