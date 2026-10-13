"""Conservative source/dependency fingerprint for immutable resumable runs."""
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path


def source_policy_hash():
    root=Path(__file__).resolve().parents[1]
    digest=sha256()
    for directory in ('domain','application','runtime','ports','infrastructure/llm','infrastructure/storage','infrastructure/sources'):
        for path in sorted(root.joinpath(directory).rglob('*.py')):
            digest.update(str(path.relative_to(root)).replace('\\','/').encode())
            digest.update(path.read_text(encoding='utf-8').replace('\r\n','\n').encode())
    for name in ('langgraph','pydantic','pypdf','sqlalchemy','httpx'):
        digest.update((name+':'+version(name)).encode())
    return digest.hexdigest()
