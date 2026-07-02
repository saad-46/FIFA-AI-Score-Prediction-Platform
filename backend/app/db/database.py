from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

# Convert postgres:// to postgresql+asyncpg://
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Kept modest on purpose: render.yaml runs this service with `--workers 2`,
    # and each worker process gets its own engine/pool. pool_size=5 + max_overflow=5
    # means at most (5+5) * 2 workers = 20 concurrent connections to Supabase,
    # which fits comfortably under Supabase's default connection caps (free/small
    # plans typically allow ~60 direct connections, less via the pgbouncer pooler).
    # Raise pool_size only after confirming the Supabase plan's connection limit.
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    connect_args={
        "ssl": "require"
    }
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
