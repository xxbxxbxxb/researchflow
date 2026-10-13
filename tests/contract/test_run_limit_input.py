import pytest
from pydantic import ValidationError

from researchflow.api.schemas import RunStart


def test_user_can_tighten_request_budget_and_invalid_limits_are_rejected():
    data=RunStart.model_validate({'project_id':'p','limits':{'max_model_calls':4,'active_timeout_seconds':30}})
    assert data.limits.max_model_calls==4
    for invalid in (17,0,True):
        with pytest.raises(ValidationError):
            RunStart.model_validate({'project_id':'p','limits':{'max_model_calls':invalid}})
