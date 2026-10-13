import importlib
import json
from dataclasses import replace

import pytest
from researchflow.application.evidence import manual_evidence
from researchflow.domain.claims import Claim
from researchflow.domain.research import Evidence
from researchflow.infrastructure.llm.errors import LLMProviderUnavailableError
from researchflow.ports.model import ChatResponse


class Judge:
    def __init__(self, status='supported', error=None, forged=False):
        self.calls = 0
        self.status = status
        self.error = error
        self.forged = forged
    async def complete(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        data = json.loads(request.messages[-1].content)
        evidences = data['evidence']
        refs = [e['evidence_id'] for e in evidences]
        quotes = [{'evidence_id':e['evidence_id'],'quote':e['text']} for e in evidences]
        if self.forged:
            refs = ['missing']
            quotes = [{'evidence_id':'missing','quote':'invented'}]
        return ChatResponse(text=json.dumps({'verifications':[{'claim_id':c['claim_id'],'status':self.status,'evidence_ids':refs,'quotes':quotes,'rationale':'A relation assessed against the provided excerpt.'} for c in data['claims']]}), model='fixture-verifier')


def verifier(model):
    if importlib.util.find_spec('researchflow.application.verification') is None:
        pytest.fail('Semantic and structural claim verification is not implemented')
    return importlib.import_module('researchflow.application.verification').ClaimVerifier(model)


def fixture(claim_text='The sample size was 12.', source_text='The sample size was 12.'):
    snapshot, evidence = manual_evidence('p', Evidence('e1','paper','p1',source_text))
    claim = Claim('c1','t1','p',claim_text,('e1',))
    return claim,evidence,snapshot


@pytest.mark.asyncio
async def test_supported_claim_has_accepted_original_evidence():
    claim,evidence,snapshot=fixture()
    results=await verifier(Judge()).verify((claim,),(evidence,),(snapshot,))
    assert results[0].status == 'supported'
    assert results[0].accepted_evidence_ids == ('e1',)
    assert ('model','fixture-verifier') in results[0].model_metadata


@pytest.mark.asyncio
@pytest.mark.parametrize('claim_text,source_text',[
    ('The sample size was 999.','The sample size was 12.'),
    ('It works in all languages.','It works only in Chinese.'),
    ('该方法适用于所有语言。','该方法仅适用于中文。')])
async def test_numeric_or_scope_expansion_cannot_be_supported(claim_text,source_text):
    claim,evidence,snapshot=fixture(claim_text,source_text)
    result=(await verifier(Judge()).verify((claim,),(evidence,),(snapshot,)))[0]
    assert result.status != 'supported'
    assert result.checks


@pytest.mark.asyncio
async def test_no_evidence_is_insufficient_and_provider_failure_is_inconclusive():
    claim,evidence,snapshot=fixture()
    model=Judge()
    result=(await verifier(model).verify((replace(claim,proposed_evidence_ids=()),),(),()))[0]
    assert result.status == 'insufficient' and model.calls == 0
    failed=(await verifier(Judge(error=LLMProviderUnavailableError('offline'))).verify((claim,),(evidence,),(snapshot,)))[0]
    assert failed.status == 'inconclusive'
    assert failed.accepted_evidence_ids == ()


@pytest.mark.asyncio
async def test_identity_and_anchor_fail_before_semantic_call():
    claim,evidence,snapshot=fixture()
    for bad in [replace(evidence, project_id='other'),replace(evidence,quote_hash='damaged')]:
        model=Judge()
        with pytest.raises(ValueError):
            await verifier(model).verify((claim,),(bad,),(snapshot,))
        assert model.calls == 0
    with pytest.raises(ValueError):
        await verifier(Judge()).verify((replace(claim,proposed_evidence_ids=('missing',)),),(evidence,),(snapshot,))


@pytest.mark.asyncio
async def test_verifier_cannot_forge_references():
    claim,evidence,snapshot=fixture()
    with pytest.raises(ValueError):
        await verifier(Judge(forged=True)).verify((claim,),(evidence,),(snapshot,))


@pytest.mark.asyncio
async def test_contradiction_is_retained_with_original_evidence():
    claim,evidence,snapshot=fixture()
    opposite_snapshot,opposite=manual_evidence('p',Evidence('e2','replication','p2','The sample size was 24.'))
    result=(await verifier(Judge('contradicted')).verify((claim,),(evidence,opposite),(snapshot,opposite_snapshot)))[0]
    assert result.status == 'contradicted'
    assert result.accepted_evidence_ids == ('e1','e2')
