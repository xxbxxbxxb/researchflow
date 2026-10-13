import pytest

from researchflow.domain.usage import ModelUsage
from researchflow.runtime import budget


def test_versioned_environment_price_is_used_and_partial_configuration_is_rejected(monkeypatch):
    monkeypatch.setenv('RF_PRICE_VERSION','fixture-usd-v1')
    monkeypatch.setenv('RF_INPUT_PRICE_PER_MILLION','1')
    monkeypatch.setenv('RF_OUTPUT_PRICE_PER_MILLION','2')
    assert hasattr(budget,'price_from_env'),'service needs an actual pricing configuration entrypoint'
    usage=budget.price_usage(ModelUsage(1000,500),budget.price_from_env())
    assert usage.estimated_cost==pytest.approx(0.002) and usage.price_version=='fixture-usd-v1'
    monkeypatch.delenv('RF_OUTPUT_PRICE_PER_MILLION')
    with pytest.raises(ValueError):
        budget.price_from_env()
