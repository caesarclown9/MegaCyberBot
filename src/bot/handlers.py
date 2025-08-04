from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from src.database import db_manager, ArticleRepository
from src.utils import LoggerMixin, MetricsMixin, TELEGRAM_MESSAGES

router = Router()


class BotHandlers(LoggerMixin, MetricsMixin):
    """Telegram bot message handlers for group mode."""
    
    @router.message(Command("status"))
    async def status_handler(self, message: Message) -> None:
        """Handle /status command - show bot status."""
        async with db_manager.get_session() as session:
            article_repo = ArticleRepository(session)
            
            # Get latest articles count
            latest_articles = await article_repo.get_latest_articles(limit=10)
            total_articles = len(latest_articles)
            
            status_text = (
                "🤖 *Статус HackerNews Bot*\n\n"
                f"📊 Всего статей в базе: {total_articles}\n"
                "⏰ Интервал проверки: каждые 2 часа\n"
                "🔄 Источник: TheHackerNews.com\n"
                "🌐 Автоперевод на русский язык\n\n"
                "📋 *Команды:*\n"
                "/status - Показать статус бота\n"
                "/latest - Последние 5 новостей\n"
                "/help - Справка"
            )
        
        await message.answer(status_text, parse_mode="Markdown")
        
        self.increment_counter(
            TELEGRAM_MESSAGES,
            {"type": "command", "status": "success"}
        )
        self.log_info("Status command used", user_id=message.from_user.id if message.from_user else None)
    
    @router.message(Command("latest"))
    async def latest_handler(self, message: Message) -> None:
        """Handle /latest command."""
        async with db_manager.get_session() as session:
            article_repo = ArticleRepository(session)
            
            # Get latest articles
            articles = await article_repo.get_latest_articles(limit=5)
        
        if not articles:
            await message.answer("📭 Пока нет доступных новостей.")
            return
        
        # Send each article
        for article in articles:
            text = self._format_article(article)
            await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)
        
        self.increment_counter(
            TELEGRAM_MESSAGES,
            {"type": "command", "status": "success"}
        )
        self.log_info("Sent latest articles", telegram_id=message.from_user.id, count=len(articles))
    
    @router.message(Command("help"))
    async def help_handler(self, message: Message) -> None:
        """Handle /help command."""
        help_text = (
            "🔐 *HackerNews Bot - Справка*\n\n"
            "Этот бот автоматически парсит новости с сайта TheHackerNews.com "
            "и переводит их на русский язык.\n\n"
            "📋 *Команды:*\n"
            "/status - Показать статус бота\n"
            "/latest - Получить последние 5 новостей\n"
            "/help - Показать эту справку\n\n"
            "🔔 *Как это работает:*\n"
            "• Бот проверяет новые статьи каждые 2 часа\n"
            "• Новые статьи автоматически переводятся на русский\n"
            "• Новости отправляются прямо в эту группу\n\n"
            "💡 *Источник:* TheHackerNews.com - ведущий сайт новостей кибербезопасности"
        )
        
        await message.answer(help_text, parse_mode="Markdown")
        
        self.increment_counter(
            TELEGRAM_MESSAGES,
            {"type": "command", "status": "success"}
        )
    
    @staticmethod
    def _format_article(article) -> str:
        """Format article for Telegram message."""
        title = article.title_ru or article.title
        description = article.description_ru or article.description or ""
        
        # Limit description length
        if len(description) > 300:
            description = description[:297] + "..."
        
        # Format date
        date_str = article.published_at.strftime("%d.%m.%Y %H:%M") if article.published_at else ""
        
        text = f"📰 *{title}*\n\n"
        
        if description:
            text += f"{description}\n\n"
        
        if date_str:
            text += f"📅 {date_str}\n"
        
        text += f"🔗 [Читать полностью]({article.url})"
        
        return text


# Create handlers instance
handlers = BotHandlers()