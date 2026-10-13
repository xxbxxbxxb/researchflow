import type { components } from './generated';

export type Schema = components['schemas'];
export type Project = Schema['Project'];
export type TaskRecord = Schema['TaskRecord'];
export type RunRecord = Schema['RunRecord'];
export type ReportVersion = Schema['ReportVersion'];
export type ResearchResult = Schema['ResearchResult'];
export type EvidenceBundle = Schema['EvidenceBundle'];
export type KnowledgeRecord = Schema['KnowledgeRecordResponse'];
export type FollowUpDraft = Schema['FollowUpDraft'];
export type Session = Schema['AuthSessionResponse'];
export type SourceSnapshot = Schema['SourceSnapshot'];
export type RunEvent = Schema['RunEventResponse'];

export class APIError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
function csrfToken() {
  return document.cookie.split('; ').find(row => row.startsWith('rf_csrf='))?.slice(8) ?? '';
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  if (options.method && !['GET','HEAD'].includes(options.method)) headers.set('X-CSRF-Token',decodeURIComponent(csrfToken()));
  const response = await fetch(path,{...options,headers,credentials:'same-origin'});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status===401 && !path.endsWith('/login')) window.dispatchEvent(new Event('rf:unauthorized'));
    throw new APIError(response.status,String(payload.code ?? 'request_failed'),String(payload.message ?? '请求暂时无法完成，请稍后重试。'));
  }
  return response.json() as Promise<T>;
}
export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string,body: unknown,key?: string) => request<T>(path,{method:'POST',body:JSON.stringify(body),headers:key?{'Idempotency-Key':key}:undefined}),
  upload: <T>(path: string,file: File) => { const form=new FormData(); form.set('file',file); return request<T>(path,{method:'POST',body:form}); }
};
export const scope = (path: string,projectId: string) => path+(path.includes('?')?'&':'?')+'project_id='+encodeURIComponent(projectId);
export const link = (kind: 'tasks'|'runs'|'reports',id: string,projectId: string) => scope('/'+kind+'/'+encodeURIComponent(id),projectId);
export const errorText = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请重试。';
export const dateText = (value: string) => new Intl.DateTimeFormat('zh-CN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
