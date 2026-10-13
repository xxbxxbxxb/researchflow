export const keys = {
  session:['session'] as const, projects:['projects'] as const,
  sources:(id:string)=>['project',id,'sources'] as const,
  tasks:(id:string)=>['project',id,'tasks'] as const,
  runs:(id:string)=>['project',id,'runs'] as const,
  reports:(id:string)=>['project',id,'reports'] as const,
  knowledge:(id:string)=>['project',id,'knowledge'] as const,
  drafts:(id:string)=>['project',id,'drafts'] as const,
  run:(id:string)=>['run',id] as const,
  report:(id:string)=>['report',id] as const,
  events:(id:string)=>['events',id] as const,
};
