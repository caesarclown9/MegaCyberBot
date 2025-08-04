from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from src.config import settings
from src.utils import get_logger, LoggerMixin
from .models import Base

logger = get_logger(__name__)


class DatabaseManager(LoggerMixin):
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def init(self) -> None:
        """Initialize the database engine and sessionmaker."""
        try:
            # Create engine with appropriate settings
            engine_kwargs = {
                "echo": settings.log_level == "DEBUG",
                "future": True,
            }
            
            # Use NullPool for SQLite to avoid connection issues
            if self.database_url.startswith("sqlite"):
                engine_kwargs["poolclass"] = NullPool
                engine_kwargs["connect_args"] = {"check_same_thread": False}
            
            self._engine = create_async_engine(self.database_url, **engine_kwargs)
            
            # Create sessionmaker
            self._sessionmaker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Create tables if they don't exist
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.log_info("Database initialized successfully", url=self.database_url)
            
        except Exception as e:
            self.log_error("Failed to initialize database", error=str(e))
            raise
    
    async def close(self) -> None:
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self.log_info("Database connection closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        if not self._sessionmaker:
            raise RuntimeError("Database not initialized. Call init() first.")
        
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with db_manager.get_session() as session:
        yield session