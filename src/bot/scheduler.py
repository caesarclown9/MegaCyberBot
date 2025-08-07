import asyncio
from datetime import datetime
from typing import Optional
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.config import settings
from src.utils import LoggerMixin, MetricsMixin, ARTICLES_PARSED
from src.database import db_manager, get_db_session, ArticleRepository
from src.parser import HackerNewsParser, CybersecurityNewsParser, RSSFeedParser
from src.utils import TranslationService
from .bot import TelegramBot


class NewsScheduler(LoggerMixin, MetricsMixin):
    """Scheduler for periodic news parsing and sending."""
    
    def __init__(self, bot: TelegramBot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.parsers = []
        self.translator = TranslationService()
        self._running = False
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        self.log_info("Starting news scheduler")
        
        # Initialize database
        await db_manager.init()
        
        # Schedule periodic parsing
        job = self.scheduler.add_job(
            func=self.parse_and_send_news,
            trigger=IntervalTrigger(minutes=settings.parse_interval_minutes),
            id="parse_news",
            name="Parse and send news",
            replace_existing=True,
            misfire_grace_time=300,  # 5 minutes grace time
            max_instances=1  # Only one instance can run at a time
        )
        
        self.log_info(
            "Scheduled parsing job",
            job_id=job.id,
            interval_minutes=settings.parse_interval_minutes,
            next_run=str(job.next_run_time)
        )
        
        # Schedule cleanup tasks
        self.scheduler.add_job(
            func=self.cleanup_old_data,
            trigger=IntervalTrigger(days=1),
            id="cleanup",
            name="Cleanup old data",
            replace_existing=True
        )
        
        # Schedule keep-alive to prevent Render from sleeping
        if settings.environment == "production":
            self.scheduler.add_job(
                func=self.keep_alive,
                trigger=IntervalTrigger(minutes=10),
                id="keep_alive",
                name="Keep alive ping",
                replace_existing=True
            )
        
        # Start scheduler
        self.scheduler.start()
        self._running = True
        
        # Run initial parse
        await self.parse_and_send_news()
        
        self.log_info("News scheduler started")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        self.log_info("Stopping news scheduler")
        
        self.scheduler.shutdown(wait=True)
        await db_manager.close()
        
        self._running = False
        
        self.log_info("News scheduler stopped")
    
    async def parse_and_send_news(self):
        """Parse news and send to users."""
        start_time = datetime.utcnow()
        
        try:
            self.log_info(
                "Starting news parsing cycle",
                time=start_time.isoformat(),
                scheduler_running=self.scheduler.running if self.scheduler else False,
                jobs_count=len(self.scheduler.get_jobs()) if self.scheduler else 0
            )
            
            async with db_manager.get_session() as session:
                article_repo = ArticleRepository(session)
                all_new_articles = []
                
                # Try RSS feeds first (most reliable)
                raw_articles = []
                try:
                    async with RSSFeedParser() as parser:
                        raw_articles = await parser.parse_articles()
                        self.log_info(f"Fetched {len(raw_articles)} articles from RSS feeds")
                except Exception as e:
                    self.log_error("RSS feeds parsing failed", error=str(e))
                
                # If RSS failed or got few articles, try HackerNews
                if len(raw_articles) < 5:
                    try:
                        async with HackerNewsParser() as parser:
                            hackernews_articles = await parser.parse_articles()
                            self.log_info(f"Fetched {len(hackernews_articles)} articles from HackerNews")
                            # Add only unique articles
                            existing_urls = {a.get("url") for a in raw_articles}
                            for article in hackernews_articles:
                                if article.get("url") not in existing_urls:
                                    raw_articles.append(article)
                    except Exception as e:
                        self.log_warning("HackerNews parsing failed", error=str(e))
                
                # If still need more articles, try alternative sources
                if len(raw_articles) < 5:
                    try:
                        async with CybersecurityNewsParser() as parser:
                            alt_articles = await parser.parse_articles()
                            self.log_info(f"Fetched {len(alt_articles)} articles from alternative sources")
                            # Add only unique articles
                            existing_urls = {a.get("url") for a in raw_articles}
                            for article in alt_articles:
                                if article.get("url") not in existing_urls:
                                    raw_articles.append(article)
                    except Exception as e:
                        self.log_warning("Alternative sources parsing failed", error=str(e))
                
                # Process articles (English - needs translation)
                for raw_article in raw_articles[:settings.max_articles_per_fetch]:
                    if await article_repo.exists(raw_article["url"]):
                        continue
                    
                    try:
                        # Store original English content
                        raw_article["title_original"] = raw_article.get("title")
                        raw_article["description_original"] = raw_article.get("description")
                        
                        # Set source if not already set
                        if not raw_article.get("source"):
                            raw_article["source"] = "HackerNews"
                        
                        # Translate to Russian
                        translated_article = await self.translator.translate_article(raw_article)
                        
                        # Store Russian translations
                        translated_article["title_ru"] = translated_article.get("title")
                        translated_article["description_ru"] = translated_article.get("description")
                        
                        article = await article_repo.create(translated_article)
                        all_new_articles.append(article)
                        
                    except Exception as e:
                        self.log_error(
                            "Failed to process article",
                            url=raw_article.get("url"),
                            error=str(e)
                        )
                        continue
                
                await session.commit()
                
                self.increment_counter(
                    ARTICLES_PARSED,
                    {"status": "success"},
                    len(all_new_articles)
                )
                
                self.log_info(
                    "Parsing cycle completed",
                    new_articles=len(all_new_articles),
                    duration=(datetime.utcnow() - start_time).total_seconds(),
                    next_run_in_minutes=settings.parse_interval_minutes
                )
                
                # Log next scheduled run
                jobs = self.scheduler.get_jobs()
                for job in jobs:
                    if job.id == "parse_news":
                        self.log_info(
                            "Next parsing scheduled",
                            job_id=job.id,
                            next_run=str(job.next_run_time),
                            pending=job.pending
                        )
                
                # Send new articles to group
                for article in all_new_articles:
                    await self.bot.send_article_to_group(article)
                    # Small delay between articles
                    await asyncio.sleep(2)
                    
        except Exception as e:
            self.log_error("Error in parsing cycle", error=str(e))
            self.increment_counter(ARTICLES_PARSED, {"status": "error"})
            
            # Notify admin about error
            await self.bot.send_admin_notification(
                f"❌ Ошибка парсинга:\n{str(e)[:200]}"
            )
    
    async def cleanup_old_data(self):
        """Clean up old articles and cache."""
        try:
            self.log_info("Starting cleanup")
            
            async with db_manager.get_session() as session:
                article_repo = ArticleRepository(session)
                
                # Clean old articles (older than 30 days)
                article_count = await article_repo.cleanup_old_articles(days=30)
                
                # Translation cache cleanup no longer needed
                cache_count = 0
                
                await session.commit()
                
                self.log_info(
                    "Cleanup completed",
                    articles_deleted=article_count,
                    cache_deleted=cache_count
                )
                
        except Exception as e:
            self.log_error("Cleanup failed", error=str(e))
    
    async def keep_alive(self):
        """Send keep-alive ping to prevent Render from sleeping."""
        try:
            # Log scheduler state
            jobs = self.scheduler.get_jobs() if self.scheduler else []
            self.log_info(
                "Keep-alive: Scheduler state",
                running=self.scheduler.running if self.scheduler else False,
                jobs_count=len(jobs),
                jobs_info=[{"id": j.id, "next_run": str(j.next_run_time), "pending": j.pending} for j in jobs]
            )
            
            # Ping our own metrics endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/metrics", timeout=5) as response:
                    if response.status == 200:
                        self.log_info("Keep-alive ping successful")
                    else:
                        self.log_warning(f"Keep-alive ping failed: {response.status}")
        except Exception as e:
            self.log_warning("Keep-alive ping failed", error=str(e))