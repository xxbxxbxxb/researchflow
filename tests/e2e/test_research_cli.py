import json
import os
import subprocess
import sys

import pytest


def command(*args):
    env={k:v for k,v in os.environ.items() if k not in ('RF_LLM_API_KEY','RF_LLM_BASE_URL','RF_LLM_MODEL')}
    return subprocess.run([sys.executable,'-m','researchflow.cli',*args],capture_output=True,text=True,env=env)


@pytest.mark.parametrize('case,status',[('supported','supported'),('contradicted','contradicted'),('insufficient',None)])
def test_fixed_cases_run_the_entire_business_pipeline(case,status):
    result=command('demo','--case',case,'--format','json')
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data['execution_mode']=='demo'
    assert data['report']['execution_mode']=='demo'
    if status:
        assert data['verifications'][0]['status']==status
    else:
        assert data['report']['conclusion_claim_ids']==[]


def test_invalid_citation_cannot_produce_a_success_report():
    result=command('demo','--case','invalid-citation','--format','json')
    assert result.returncode!=0
    assert json.loads(result.stdout)['error']['code']=='invalid_output'


def test_live_configuration_missing_is_not_silently_a_fake():
    result=command('research','--input','examples/supported.json','--mode','live','--format','json')
    assert result.returncode!=0
    assert json.loads(result.stdout)['error']['code']=='configuration_missing'
