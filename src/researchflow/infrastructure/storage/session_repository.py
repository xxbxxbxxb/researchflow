import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from researchflow.domain.access import Principal
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import LoginGuardRow, SessionRow


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class LoginRateLimitedError(RuntimeError):
    pass


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def begin_login(self, source: str) -> str:
        key = token_hash(source)
        async with self.database.session.begin() as session:
            now = cast(datetime,await session.scalar(select(func.clock_timestamp())))
            await session.execute(insert(LoginGuardRow).values(source_key=key,window_started=now,failures=0,pending=0).on_conflict_do_nothing())
            row = (await session.scalars(select(LoginGuardRow).where(LoginGuardRow.source_key==key).with_for_update())).one()
            if row.window_started + timedelta(minutes=1) <= now:
                row.window_started,row.failures,row.pending = now,0,0
            if row.failures+row.pending >= 5:
                raise LoginRateLimitedError('login failures exceed five per minute')
            row.pending += 1
            return key

    async def end_login(self, key: str, success: bool) -> None:
        async with self.database.session.begin() as session:
            row = (await session.scalars(select(LoginGuardRow).where(LoginGuardRow.source_key==key).with_for_update())).one()
            row.pending = max(0,row.pending-1)
            if not success:
                row.failures += 1

    async def create(self, actor_id: str = 'local-user') -> tuple[str,str]:
        token,csrf = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        async with self.database.session.begin() as session:
            now = cast(datetime,await session.scalar(select(func.clock_timestamp())))
            await session.execute(delete(SessionRow).where(SessionRow.expires_at <= now))
            session.add(SessionRow(token_hash=token_hash(token),actor_id=actor_id,csrf_hash=token_hash(csrf),expires_at=now+timedelta(hours=8)))
        return token,csrf

    async def lookup(self, token: str):
        if not token or len(token)>128:
            return None
        async with self.database.session() as session:
            now = cast(datetime,await session.scalar(select(func.clock_timestamp())))
            row = await session.get(SessionRow,token_hash(token))
            if row is None or row.expires_at <= now:
                return None
            return Principal(row.actor_id),row.csrf_hash

    async def revoke(self, token: str) -> None:
        async with self.database.session.begin() as session:
            await session.execute(delete(SessionRow).where(SessionRow.token_hash==token_hash(token)))
