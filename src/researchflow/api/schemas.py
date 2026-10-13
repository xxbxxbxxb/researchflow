from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)


class LoginInput(StrictInput):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=1,max_length=1024,repr=False)


class ProjectInput(StrictInput):
    name: str = Field(min_length=1,max_length=200)
    background: str = Field(default='',max_length=10000)


class TaskInput(StrictInput):
    question: str = Field(min_length=1,max_length=5000)
    source_ids: list[str] = Field(default_factory=list,max_length=100)
    parent_task_id: str | None = None


class RunStart(StrictInput):
    project_id: str = Field(min_length=1,max_length=200)
    mode: Literal['demo','live'] | None = None
    driver: Literal['fixed'] = 'fixed'
    demo_case: Literal['supported','contradicted','insufficient','invalid-citation'] = 'supported'


class URLInput(StrictInput):
    url: str = Field(min_length=1,max_length=5000)


class ResumeInput(StrictInput):
    input_version: str | None = None


class ReviewInput(StrictInput):
    action: Literal['approve','reject']
    comment: str = Field(default='',max_length=2000)
