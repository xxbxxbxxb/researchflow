import importlib
from datetime import UTC, datetime

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.claims import Claim, Verification
from researchflow.domain.research import Evidence


def api():
    if importlib.util.find_spec('researchflow.application.reports') is None:
        pytest.fail('Traceable report construction is not implemented')
    return importlib.import_module('researchflow.application.reports'),importlib.import_module('researchflow.domain.reports')


def verdict(claim,status,refs):
    return Verification('v'+claim.claim_id,claim.claim_id,status,refs,'Evidence relation.',(), 'v1',(),datetime.now(UTC))


def test_only_supported_claims_enter_the_answer_with_traceable_links():
    app,types=api()
    _,evidence=manual_evidence('p',Evidence('e1','source','p1','Sample was 12.'))
    a=Claim('a','t','p','Sample was 12.',('e1',))
    b=Claim('b','t','p','Sample was 999.',('e1',))
    report=app.ReportBuilder().build(types.ReportInputs('p','t','run',(a,b),(verdict(a,'supported',('e1',)),verdict(b,'contradicted',('e1',))),(evidence,),('Need replication.',)))
    assert report.conclusion_claim_ids == ('a',)
    assert report.finding_claim_ids == ('b',)
    assert report.source_evidence_ids == ('e1',)
    assert '/api/evidence/e1' in report.markdown
    assert '相反' in report.markdown


def test_empty_research_is_an_explicit_insufficient_report():
    app,types=api()
    report=app.ReportBuilder().build(types.ReportInputs('p','t','run',(),(),(),('Please add sources.',)))
    assert report.conclusion_claim_ids == ()
    assert '证据不足' in report.markdown


def test_report_rejects_missing_or_forged_verification_links():
    app,types=api()
    claim=Claim('a','t','p','claim',('e1',))
    for verifications in [(),(verdict(claim,'supported',('missing',)),)]:
        with pytest.raises(ValueError):
            app.ReportBuilder().build(types.ReportInputs('p','t','run',(claim,),verifications,(),()))
