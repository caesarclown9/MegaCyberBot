"""
Alternative database connection module optimized for Supabase.
Use this if you have connection issues with the main connection.py
"""
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from src.config import settings
from src.utils import get_logger, LoggerMixin
from .models import Base
import socket

logger = get_logger(__name__)


def force_ipv4():
    """Force IPv4 connections only."""
    # Monkey patch socket to prefer IPv4
    original_getaddrinfo = socket.getaddrinfo
    
    def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        # Force IPv4
        family = socket.AF_INET
        return original_getaddrinfo(host, port, family, type, proto, flags)
    
    socket.getaddrinfo = getaddrinfo_ipv4_only


class DatabaseManager(LoggerMixin):
    """Manages database connections and sessions optimized for Supabase."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
        
        # Force IPv4 for Supabase
        force_ipv4()
    
    async def init(self) -> None:
        """Initialize the database engine and sessionmaker."""
        try:
            # Parse and potentially modify the database URL for better compatibility
            url = self.database_url
            
            # If using Supabase direct connection (not pooler), switch to pooler if possible
            if "supabase.co" in url and "pooler" not in url:
                self.log_warning("Using direct Supabase connection. Consider using pooler for better stability.")
            
            # Create engine with Supabase-optimized settings
            engine_kwargs = {
                "echo": settings.log_level == "DEBUG",
                "future": True,
                # Use NullPool to avoid connection pooling issues
                "poolclass": NullPool,
                # Connection settings optimized for Supabase
                "connect_args": {
                    "server_settings": {
                        "application_name": "MegaCyberBot",
                        "jit": "off"  # Disable JIT for compatibility
                    },
                    "command_timeout": 60,
                    "timeout": 30,
                    # SSL settings for Supabase
                    "ssl": "require" if "supabase" in url else "prefer",
                }
            }
            
            # For pooler connections, use different settings
            if "pooler.supabase.com" in url:
                # Pooler handles connection pooling, so we use NullPool
                engine_kwargs["poolclass"] = NullPool
                self.log_info("Using Supabase pooler connection")
            else:
                # For direct connections, add pool settings
                engine_kwargs.update({
                    "pool_pre_ping": True,
                    "pool_recycle": 300,
                    "pool_size": 2,  # Keep small for Supabase
                    "max_overflow": 3
                })
            
            self._engine = create_async_engine(url, **engine_kwargs)
            
            # Create sessionmaker
            self._sessionmaker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Test the connection
            async with self._engine.begin() as conn:
                # Create tables if they don't exist
                await conn.run_sync(Base.metadata.create_all)
                # Test query
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            
            self.log_info("Database initialized successfully (Supabase optimized)", 
                         pooler="pooler" in url,
                         ssl="require" if "supabase" in url else "prefer")
            
        except Exception as e:
            self.log_error("Failed to initialize database", error=str(e))
            # Try to provide helpful error messages
            if "Connect call failed" in str(e):
                self.log_error("Connection failed. Check if DATABASE_URL is correct and Supabase is accessible.")
            elif "password authentication failed" in str(e):
                self.log_error("Authentication failed. Check your database password.")
            elif "timeout" in str(e).lower():
                self.log_error("Connection timeout. Supabase might be unreachable or slow.")
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