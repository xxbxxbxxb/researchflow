"""Release evidence from real subprocesses/JUnit reports, never optimistic constants."""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

SCENARIOS={
    'A01':('test_document_parsing','test_hybrid_retrieval'),
    'A02':('test_claim_verification','test_report_builder'),
    'A03':('test_claim_extraction','test_research_repository'),
    'A04':('test_fixed_worker','test_research_cli'),
    'A05':('test_evidence_ledger','test_step_commit'),
    'A06':('test_provider_hardening','test_model_runtime'),
    'A07':('test_cancel_late_result','test_stream_commit_boundary'),
    'A08':('test_worker_restart','test_fenced_checkpoint'),
    'A09':('test_run_fencing','test_fenced_checkpoint'),
    'A10':('test_event_stream',),
    'A11':('test_project_knowledge','test_follow_up_start'),
    'A12':('test_project_knowledge',),
    'A13':('test_tool_authorization','test_minimal_react'),
    'A14':('test_safe_fetch','test_api_authorization','test_tool_authorization'),
    'A15':('test_evaluation_modes','test_task_api'),
    'A16':('test_research_repository','test_worker_restart'),
}


def combine(statuses):
    for status in ('failed','blocked','not_run'):
        if status in statuses:
            return status
    return 'passed' if statuses else 'not_run'


def scenario_status(report: Path,patterns):
    if not report.exists():
        return 'not_run'
    tree=ET.parse(report)
    statuses=[]
    for pattern in patterns:
        cases=[case for case in tree.iter('testcase') if pattern in case.get('classname','') or pattern in case.get('file','')]
        if not cases:
            statuses.append('not_run')
        for case in cases:
            statuses.append('failed' if case.find('failure') is not None or case.find('error') is not None else 'blocked' if case.find('skipped') is not None else 'passed')
    return combine(statuses)


def command(root,output,name,args):
    output.mkdir(parents=True,exist_ok=True)
    log=output/(name+'.log')
    started=datetime.now(UTC).isoformat()
    with log.open('w') as f:
        try:
            result=subprocess.run(args,cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=600)
            code=result.returncode
            status='passed' if code==0 else 'failed'
        except (OSError,subprocess.TimeoutExpired):
            code=None
            status='blocked'
    return {'status':status,'returncode':code,'command':args,'started_at':started,'log':str(log)}


def validate(output: Path,existing_results=False,root: Path | None=None):
    root=(root or Path(__file__).resolve().parents[2]).resolve()
    output=output.resolve()
    checks={}
    junit=root/'artifacts/python.xml'
    if not existing_results:
        checks['python']=command(root,output,'python',[sys.executable,'-m','pytest','-q','--junitxml='+str(junit)])
        checks['ruff']=command(root,output,'ruff',[sys.executable,'-m','ruff','check','.'])
        checks['mypy']=command(root,output,'mypy',[sys.executable,'-m','mypy','src/researchflow'])
        npm='npm.cmd' if os.name=='nt' else 'npm'
        checks['web_types']=command(root,output,'web-types',[npm,'--prefix','web','run','typecheck'])
        checks['web_build']=command(root,output,'web-build',[npm,'--prefix','web','run','build'])
        if os.getenv('RF_TEST_DATABASE_URL'):
            checks['browser']=command(root,output,'browser',[npm,'--prefix','web','run','test:e2e'])
        else:
            checks['browser']={'status':'blocked','reason':'real_postgresql_unavailable'}
    scenarios={name:{'status':scenario_status(junit,patterns),'report':str(junit)} for name,patterns in SCENARIOS.items()}
    browser=root/'artifacts/playwright.xml'
    browser_status=scenario_status(browser,('research.spec.ts','state-preservation.spec.ts'))
    for name in ('A01','A04','A10','A11','A12'):
        scenarios[name]['status']=combine((scenarios[name]['status'],browser_status))
    compose=root/'artifacts/compose-smoke.json'
    compose_status=json.loads(compose.read_text())['status'] if compose.exists() else 'not_run'
    scenarios['A16']['status']=combine((scenarios['A16']['status'],compose_status))
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        revision='source-distribution'
    manifest={'status':combine([v['status'] for v in scenarios.values()]+[c['status'] for c in checks.values()]),'revision':revision,'created_at':datetime.now(UTC).isoformat(),'python':sys.version.split()[0],'checks':checks,'scenarios':scenarios,'live_quality':{'status':'not_run','reason':'separate_live_evaluation_required'}}
    output.mkdir(parents=True,exist_ok=True)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
