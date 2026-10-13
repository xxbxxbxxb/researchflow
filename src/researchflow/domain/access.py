from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    actor_id: str
    project_ids: tuple[str,...] | None = None

    def allows(self, project_id: str) -> bool:
        return self.project_ids is None or project_id in self.project_ids
