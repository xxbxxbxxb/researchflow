import importlib

import pytest


def module():
    try:
        return importlib.import_module('researchflow.evaluation.metrics')
    except ModuleNotFoundError:
        pytest.fail('fixed-denominator evaluation metrics are not implemented')


def test_supported_precision_uses_false_supports_and_does_not_drop_failed_cases():
    metrics=module()
    from researchflow.evaluation.dataset import Prediction
    result=metrics.compute_metrics((Prediction('a','supported','supported',('e',),('e',)),Prediction('b','contradicted','supported',('e',),('e',)),Prediction('c','insufficient','failed'),Prediction('d','supported','inconclusive')))
    assert result.supported_precision==0.5
    assert result.supported_recall==0.5
    assert result.total==4 and result.completed==2
    assert result.confusion_matrix['contradicted']['supported']==1
    assert result.confusion_matrix['insufficient']['failed']==1
    assert result.unsupported_as_supported==('b',)


def test_no_predicted_support_is_unknown_precision_not_perfect():
    metrics=module()
    from researchflow.evaluation.dataset import Prediction
    result=metrics.compute_metrics((Prediction('a','supported','insufficient'),))
    assert result.supported_precision is None and result.supported_recall==0.0

