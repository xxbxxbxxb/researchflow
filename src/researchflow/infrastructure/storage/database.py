from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        if not url.startswith('postgresql+psycopg://'):
            raise ValueError('ResearchFlow requires PostgreSQL with psycopg')
        self.url = url
        self.engine = create_async_engine(url,pool_pre_ping=True,pool_size=10,max_overflow=10)
        self.session = async_sessionmaker(self.engine,expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()
