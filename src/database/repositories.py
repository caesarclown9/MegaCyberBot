from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils import LoggerMixin, MetricsMixin
from .models import Article, User


class BaseRepository(LoggerMixin, MetricsMixin):
    """Base repository with common database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session


class ArticleRepository(BaseRepository):
    """Repository for article operations."""
    
    async def create(self, article_data: Dict[str, Any]) -> Article:
        """Create a new article."""
        article = Article(**article_data)
        self.session.add(article)
        await self.session.flush()
        self.log_info("Article created", article_id=article.id, url=article.url)
        return article
    
    async def get_by_url(self, url: str) -> Optional[Article]:
        """Get article by URL."""
        result = await self.session.execute(
            select(Article).where(Article.url == url)
        )
        return result.scalar_one_or_none()
    
    async def get_unsent_articles(self, limit: int = 10) -> List[Article]:
        """Get articles that haven't been sent yet."""
        result = await self.session.execute(
            select(Article)
            .where(Article.is_sent == False)
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_latest_articles(self, limit: int = 5) -> List[Article]:
        """Get latest articles."""
        result = await self.session.execute(
            select(Article)
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def mark_as_sent(self, article_id: int) -> None:
        """Mark article as sent."""
        await self.session.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(is_sent=True, sent_at=datetime.utcnow())
        )
        self.log_info("Article marked as sent", article_id=article_id)
    
    async def exists(self, url: str) -> bool:
        """Check if article with given URL exists."""
        result = await self.session.execute(
            select(func.count()).select_from(Article).where(Article.url == url)
        )
        return result.scalar() > 0
    
    async def cleanup_old_articles(self, days: int = 30) -> int:
        """Delete articles older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            delete(Article).where(Article.parsed_at < cutoff_date)
        )
        count = result.rowcount
        self.log_info("Cleaned up old articles", count=count, days=days)
        return count
    
    async def mark_as_pending(self, article_id: int) -> None:
        """Mark article as pending (to be sent later after quiet hours)."""
        await self.session.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(is_sent=False, sent_at=None)  # Keep is_sent=False but clear sent_at
        )
        self.log_info("Article marked as pending", article_id=article_id)
    
    async def get_pending_articles(self, limit: int = 20) -> List[Article]:
        """Get articles that are pending to be sent (not sent and older than 1 hour)."""
        # Get articles that haven't been sent and were parsed more than 1 hour ago
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        result = await self.session.execute(
            select(Article)
            .where(and_(
                Article.is_sent == False,
                Article.parsed_at < one_hour_ago
            ))
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class UserRepository(BaseRepository):
    """Repository for user operations."""
    
    async def create_or_update(self, user_data: Dict[str, Any]) -> User:
        """Create or update user."""
        telegram_id = user_data["telegram_id"]
        
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            for key, value in user_data.items():
                setattr(user, key, value)
            user.last_seen_at = datetime.utcnow()
            self.log_info("User updated", telegram_id=telegram_id)
        else:
            # Create new user
            user = User(**user_data)
            self.session.add(user)
            self.log_info("User created", telegram_id=telegram_id)
        
        await self.session.flush()
        return user
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active_users(self) -> List[User]:
        """Get all active users."""
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return list(result.scalars().all())
    
    async def deactivate(self, telegram_id: int) -> bool:
        """Deactivate user."""
        result = await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        success = result.rowcount > 0
        if success:
            self.log_info("User deactivated", telegram_id=telegram_id)
        return success
    
    async def activate(self, telegram_id: int) -> bool:
        """Activate user."""
        result = await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_active=True, updated_at=datetime.utcnow())
        )
        success = result.rowcount > 0
        if success:
            self.log_info("User activated", telegram_id=telegram_id)
        return success
    
    async def count_active_users(self) -> int:
        """Count active users."""
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.is_active == True)
        )
        return result.scalar()


