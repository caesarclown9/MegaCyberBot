from typing import Optional
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from src.config import settings
from src.utils import LoggerMixin, MetricsMixin, TELEGRAM_MESSAGES, ACTIVE_USERS
from src.database import db_manager, UserRepository, ArticleRepository
from .handlers import router


class TelegramBot(LoggerMixin, MetricsMixin):
    """Main Telegram bot class."""
    
    def __init__(self):
        self.bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        self.dp = Dispatcher(storage=MemoryStorage())
        self.dp.include_router(router)
        self._setup_middlewares()
    
    def _setup_middlewares(self):
        """Setup bot middlewares."""
        # Add logging middleware
        @self.dp.message.middleware()
        async def log_middleware(handler, event, data):
            self.log_debug(
                "Processing message",
                user_id=event.from_user.id if event.from_user else None,
                text=event.text[:50] if event.text else None
            )
            return await handler(event, data)
    
    async def start(self):
        """Start the bot."""
        try:
            self.log_info("Starting Telegram bot")
            
            # Delete webhook to use polling
            await self.bot.delete_webhook(drop_pending_updates=True)
            
            # Start polling (this will block, so it should be called in a task)
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            self.log_error("Failed to start bot", error=str(e))
            raise
    
    async def stop(self):
        """Stop the bot."""
        try:
            self.log_info("Stopping Telegram bot")
            await self.dp.stop_polling()
            await self.bot.session.close()
        except Exception as e:
            self.log_error("Error stopping bot", error=str(e))
    
    async def send_article_to_group(self, article, target_group: str = "general"):
        """Send article to configured Telegram group based on category.
        
        Args:
            article: Article object to send
            target_group: 'general' or 'vulnerabilities' to determine which group to send to
        """
        async with db_manager.get_session() as session:
            article_repo = ArticleRepository(session)
            
            # Determine which group and topic to send to
            if target_group == "vulnerabilities":
                # Use vulnerabilities group if configured, otherwise use main group
                group_id = settings.telegram_vulnerabilities_group_id or settings.telegram_group_id
                group_type = "vulnerabilities"
                # Use vulnerabilities topic if configured
                topic_id = settings.telegram_vulnerabilities_topic_id
            else:
                group_id = settings.telegram_group_id
                group_type = "general"
                topic_id = settings.telegram_topic_id
            
            self.log_info(
                "Sending article to group",
                article_id=article.id,
                group_id=group_id,
                group_type=group_type,
                topic_id=topic_id,
                category=getattr(article, 'category', 'unknown')
            )
            
            # Format article text
            text = self._format_article(article)
            
            try:
                # Send to group
                message_params = {
                    "chat_id": group_id,
                    "text": text,
                    "parse_mode": ParseMode.MARKDOWN,
                    "disable_web_page_preview": True
                }
                
                # Add topic_id if configured for forum supergroups
                if topic_id:
                    message_params["message_thread_id"] = topic_id
                
                await self.bot.send_message(**message_params)
                
                # Mark article as sent
                await article_repo.mark_as_sent(article.id)
                await session.commit()
                
                self.increment_counter(
                    TELEGRAM_MESSAGES,
                    {"type": "group_post", "status": "success", "group": group_type}
                )
                
                self.log_info(
                    "Article sent to group successfully",
                    article_id=article.id,
                    group_type=group_type
                )
                
            except Exception as e:
                self.log_error(
                    "Failed to send article to group",
                    article_id=article.id,
                    group_id=group_id,
                    group_type=group_type,
                    error=str(e)
                )
                
                self.increment_counter(
                    TELEGRAM_MESSAGES,
                    {"type": "group_post", "status": "error", "group": group_type}
                )
                
                raise
    
    def _format_article(self, article) -> str:
        """Format article for Telegram message."""
        title = article.title_ru or article.title
        description = article.description_ru or article.description or ""
        
        # Limit description length
        if len(description) > 300:
            description = description[:297] + "..."
        
        # Format date
        date_str = article.published_at.strftime("%d.%m.%Y %H:%M") if article.published_at else ""
        
        # Source icon and name
        source_info = ""
        if hasattr(article, 'source') and article.source:
            source_icons = {
                "HackerNews": "🇺🇸 The Hacker News",
                "BleepingComputer": "💻 BleepingComputer",
                "SecurityWeek": "🔒 SecurityWeek", 
                "InfoSecurity Magazine": "📊 InfoSecurity Magazine",
                "KrebsOnSecurity": "🔍 Krebs on Security",
                "DarkReading": "🌐 Dark Reading",
                "Threatpost": "⚠️ Threatpost",
                "CSOOnline": "👔 CSO Online",
                "SecurityAffairs": "🛡️ Security Affairs"
            }
            source_info = source_icons.get(article.source, f"📰 {article.source}")
        
        text = f"📰 *{title}*\n\n"
        
        if description:
            text += f"{description}\n\n"
        
        # Add source info
        if source_info:
            text += f"📍 {source_info}\n"
        
        if date_str:
            text += f"📅 {date_str}\n"
        
        text += f"🔗 [Читать полностью]({article.url})"
        
        # If this is a translated article, add a note
        if (hasattr(article, 'title_original') and article.title_original and 
            hasattr(article, 'source') and article.source == "HackerNews"):
            text += "\n\n_Переведено с английского_"
        
        return text
    
    async def send_admin_notification(self, text: str, admin_id: Optional[int] = None):
        """Send notification to admin."""
        if not admin_id:
            return
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=f"⚙️ *Системное уведомление*\n\n{text}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            self.log_error("Failed to send admin notification", error=str(e))