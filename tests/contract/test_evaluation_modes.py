import importlib

import pytest


def module():
    try:
        return importlib.import_module('researchflow.evaluation.runner')
    except ModuleNotFoundError:
        pytest.fail('contract/live evaluation separation is missing')


@pytest.mark.asyncio
async def test_contract_results_cannot_claim_real_quality_and_missing_live_credentials_are_not_run(tmp_path,monkeypatch):
    runner=module()
    from researchflow.evaluation.dataset import load_split
    cases=load_split('development')
    for name in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL','RF_CONTEXT_WINDOW'):
        monkeypatch.delenv(name,raising=False)
    fixture=await runner.EvaluationRunner().run(cases,'contract',tmp_path/'contract')
    assert fixture.quality_measured is False and len(fixture.predictions)==12
    live=await runner.EvaluationRunner().run(cases,'live',tmp_path/'live')
    assert live.status=='not_run' and live.quality_measured is False
    assert live.total_cases==12 and live.metrics is None


def test_dataset_labels_have_traceable_disjoint_claims_documents_and_hashes():
    module()
    from researchflow.evaluation.dataset import load_split, validate_splits
    dev,holdout=load_split('development'),load_split('holdout')
    validate_splits(dev,holdout)
    assert len(dev)==len(holdout)==12
    assert {c.claim_id for c in dev}.isdisjoint(c.claim_id for c in holdout)
    assert {c.doc_id for c in dev}.isdisjoint(c.doc_id for c in holdout)
    assert all(c.source_split in ('train','dev') and c.source_hash for c in (*dev,*holdout))
    with pytest.raises(ValueError):
        validate_splits(dev,dev)
