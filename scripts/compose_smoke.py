"""Create an owned disposable Compose project; verify durable product data on restart."""
import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from argon2 import PasswordHasher

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.e2e_services import demo_pdf  # noqa: E402


async def smoke(env,compose):
    origin='http://localhost:18080'
    async with httpx.AsyncClient(base_url=origin,timeout=30,trust_env=False,headers={'Origin':origin}) as client:
        async def ready():
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                try:
                    if (await client.get('/health')).status_code==200:
                        return
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.5)
            raise RuntimeError('Compose API did not become healthy')
        await ready()
        async def post(path,data):
            r=await client.post(path,json=data)
            r.raise_for_status()
            return r.json()
        login=await post('/api/auth/login',{'password':env['RF_SMOKE_PASSWORD']})
        client.headers['X-CSRF-Token']=login['csrf_token']
        project=await post('/api/projects',{'name':'Compose restart verification','background':'Owned synthetic CI fixture'})
        pid=project['project_id']
        pdf=ROOT/'artifacts/compose-demo.pdf'
        demo_pdf(pdf)
        r=await client.post('/api/projects/'+pid+'/sources',files={'file':('demo.pdf',pdf.read_bytes(),'application/pdf')})
        r.raise_for_status()
        source=r.json()
        task=await post('/api/projects/'+pid+'/tasks',{'question':'synthetic study sample size','source_ids':[source['snapshot_id']]})
        client.headers['Idempotency-Key']='compose-'+uuid4().hex
        record=await post('/api/tasks/'+task['task_id']+'/runs',{'project_id':pid,'mode':'demo','driver':'graph'})
        client.headers.pop('Idempotency-Key')
        run_id=record['run_id']
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            run=(await client.get(f'/api/runs/{run_id}',params={'project_id':pid})).json()
            if run['state']=='succeeded':
                break
            if run['state']=='failed':
                raise RuntimeError('Compose research failed: '+str(run['error_code']))
            await asyncio.sleep(0.3)
        assert run['state']=='succeeded'
        reports=(await client.get('/api/projects/'+pid+'/reports')).json()
        report=reports[0]
        result=(await client.get('/api/reports/'+report['report_id'],params={'project_id':pid})).json()
        supported=next(v for v in result['verifications'] if v['status']=='supported')
        entry=await post('/api/projects/'+pid+'/knowledge/accept',{'verification_id':supported['verification_id']})
        before=(await client.get(f"/api/projects/{pid}/sources/{source['snapshot_id']}/original")).content
        assert before==pdf.read_bytes()
        await asyncio.to_thread(subprocess.run,[*compose,'restart','db','api','worker'],env=env,cwd=ROOT,check=True,capture_output=True)
        await ready()
        after=(await client.get(f"/api/projects/{pid}/sources/{source['snapshot_id']}/original")).content
        assert after==before
        restored=(await client.get('/api/reports/'+report['report_id'],params={'project_id':pid})).json()
        assert restored['report']['report_id']==report['report_id']
        knowledge=(await client.get('/api/projects/'+pid+'/knowledge')).json()
        assert any(k['entry']['knowledge_id']==entry['knowledge_id'] for k in knowledge)
        count=await asyncio.to_thread(subprocess.run,[*compose,'exec','-T','db','psql','-U','researchflow','-d','researchflow','-Atc','SELECT count(*) FROM graph_checkpoints'],env=env,cwd=ROOT,check=True,capture_output=True,text=True)
        assert int(count.stdout.strip())>0
        return {'status':'passed','run_id':run_id,'report_id':report['report_id'],'snapshot_hash':source['content_hash'],'persisted_checkpoints':int(count.stdout.strip()),'restart':'database/api/worker','verification':'real Compose containers and original Blob bytes'}


def main():
    artifacts=ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    password=secrets.token_urlsafe(18)
    env={**os.environ,'RF_POSTGRES_PASSWORD':secrets.token_urlsafe(18),'RF_PASSWORD_HASH':PasswordHasher().hash(password),'RF_SMOKE_PASSWORD':password,'RF_MODE':'demo','RF_BIND_PORT':'18080','RF_ALLOWED_ORIGINS':'http://localhost:18080'}
    compose=['docker','compose','--project-name','rf-smoke-'+uuid4().hex[:8]]
    result={'status':'failed'}
    try:
        subprocess.run([*compose,'up','--build','-d'],cwd=ROOT,env=env,check=True)
        result=asyncio.run(smoke(env,compose))
    finally:
        (artifacts/'compose-smoke.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        subprocess.run([*compose,'down','--volumes'],cwd=ROOT,env=env,check=False,capture_output=True)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
