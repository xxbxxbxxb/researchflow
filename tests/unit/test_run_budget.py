import importlib

import pytest


def module():
    try:
        return importlib.import_module('researchflow.runtime.budget')
    except ModuleNotFoundError:
        pytest.fail('shared run budget is not implemented')


def test_defaults_and_model_tool_step_limits_never_refund_unknown_attempts():
    m=module()
    limits=m.RunLimits()
    assert (limits.max_steps,limits.max_tool_calls,limits.max_model_calls,limits.max_concurrency)==(12,20,16,4)
    assert (limits.active_timeout_seconds,limits.operation_timeout_seconds)==(300,60)
    budget=m.RunBudget(limits=limits)
    for _ in range(16):
        budget=budget.reserve('model')
    with pytest.raises(m.BudgetExceededError):
        budget.reserve('model')
    assert budget.model_calls_used==16
    for _ in range(20):
        budget=budget.reserve('tool')
    with pytest.raises(m.BudgetExceededError):
        budget.reserve('tool')
    for _ in range(12):
        budget=budget.reserve('step')
    with pytest.raises(m.BudgetExceededError):
        budget.reserve('step')


@pytest.mark.parametrize('field,value',[('max_model_calls',True),('max_model_calls',17),('max_concurrency',5),('operation_timeout_seconds',float('inf')),('active_timeout_seconds',float('nan'))])
def test_limits_reject_nonfinite_and_unbounded_configuration(field,value):
    m=module()
    with pytest.raises(ValueError):
        m.RunLimits(**{field:value})


def test_usage_unknown_is_not_zero_and_prices_require_known_token_counts():
    m=module()
    from researchflow.domain.usage import ModelUsage
    usage=ModelUsage()
    assert usage.input_tokens is None and usage.output_tokens is None and usage.estimated_cost is None
    price=m.PriceConfig('fixture-usd-v1',1.0,2.0)
    assert m.price_usage(usage,price).estimated_cost is None
    priced=m.price_usage(ModelUsage(1000,500),price)
    assert priced.estimated_cost==pytest.approx(0.002) and priced.price_version=='fixture-usd-v1'
    assert m.price_usage(ModelUsage(1000,500),None).estimated_cost is None
