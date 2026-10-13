class EvidenceConflict(ValueError):
    """One evidence identity has conflicting immutable content."""


class ProjectBoundaryError(ValueError):
    """A reference crosses the authorized project boundary."""
