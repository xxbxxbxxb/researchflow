import os
import re
import tempfile
from hashlib import sha256
from pathlib import Path


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True,exist_ok=True)

    def path(self, content_hash: str) -> Path:
        if not re.fullmatch('[0-9a-f]{64}',content_hash):
            raise ValueError('invalid content hash')
        path = (self.root/content_hash[:2]/content_hash).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('blob path escaped storage root')
        return path

    def put(self, data: bytes) -> str:
        key = sha256(data).hexdigest()
        target = self.path(key)
        if target.exists():
            self.get(key)
            return key
        target.parent.mkdir(parents=True,exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as file:
                temp = Path(file.name)
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp,target)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return key

    def get(self, content_hash: str) -> bytes:
        data = self.path(content_hash).read_bytes()
        if sha256(data).hexdigest() != content_hash:
            raise ValueError('stored source content is corrupted')
        return data
