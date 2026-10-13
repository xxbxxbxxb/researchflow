import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    password_hash: str | None = field(default=None,repr=False)
    allowed_origins: tuple[str,...] = ('http://127.0.0.1:8000','http://localhost:8000','http://localhost:5173','http://127.0.0.1:5173')
    blob_root: Path = Path('.researchflow-data/blobs')
    execution_mode: Literal['demo','live'] = 'demo'
    secure_cookies: bool = False
    llm_base_url: str = ''
    llm_api_key: str = field(default='',repr=False)
    llm_model: str = ''
    context_window: int | None = None
    preview_enabled: bool = False

    def __post_init__(self) -> None:
        if self.execution_mode not in {'demo','live'}:
            raise ValueError('execution_mode must be demo or live')
        if self.password_hash is not None and not self.password_hash.startswith('$argon2id$'):
            raise ValueError('RF_PASSWORD_HASH must be an Argon2id hash')

    def validate_binding(self, host: str) -> None:
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host == 'localhost'
        if not local and not self.password_hash:
            raise ValueError('authentication must be configured before non-loopback binding')

    @property
    def live_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model and self.context_window is not None and self.context_window>4096)

    @classmethod
    def from_env(cls) -> 'Settings':
        url = os.getenv('RF_DATABASE_URL')
        if not url:
            raise ValueError('RF_DATABASE_URL is required')
        origins = os.getenv('RF_ALLOWED_ORIGINS')
        context = os.getenv('RF_CONTEXT_WINDOW')
        return cls(database_url=url,password_hash=os.getenv('RF_PASSWORD_HASH') or None,allowed_origins=tuple(x.strip() for x in origins.split(',') if x.strip()) if origins else ('http://127.0.0.1:8000','http://localhost:8000','http://localhost:5173','http://127.0.0.1:5173'),blob_root=Path(os.getenv('RF_BLOB_ROOT','.researchflow-data/blobs')),execution_mode=cast(Literal['demo','live'],os.getenv('RF_MODE','demo')),secure_cookies=os.getenv('RF_SECURE_COOKIES','false').lower()=='true',llm_base_url=os.getenv('RF_LLM_BASE_URL',''),llm_api_key=os.getenv('RF_LLM_API_KEY',''),llm_model=os.getenv('RF_LLM_MODEL',''),context_window=int(context) if context else None,preview_enabled=os.getenv('RF_PREVIEW_ENABLED','false').lower()=='true')
