from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    name: str
    background: str = ''

    def __post_init__(self) -> None:
        if not self.project_id.strip() or not self.name.strip() or len(self.name) > 200:
            raise ValueError('project identity and name are required; name limit is 200')


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    project_id: str
    question: str
    source_ids: tuple[str, ...] = ()
    parent_task_id: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.project_id.strip() or not self.question.strip() or len(self.question.strip()) > 5000:
            raise ValueError('task identity, project and a question of at most 5000 characters are required')
        object.__setattr__(self, 'question', self.question.strip())
        object.__setattr__(self, 'source_ids', tuple(self.source_ids))
