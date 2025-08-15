import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.config import settings
from src.utils import LoggerMixin, MetricsMixin, ARTICLES_PARSED
from src.database import db_manager, get_db_session, ArticleRepository
from src.parser import HackerNewsParser, CybersecurityNewsParser, RSSFeedParser
from src.utils import TranslationService
from src.utils.categorizer import ArticleCategorizer, ArticleCategory
from .bot import TelegramBot


class NewsScheduler(LoggerMixin, MetricsMixin):
    """Scheduler for periodic news parsing and sending."""
    
    def __init__(self, bot: TelegramBot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.parsers = []
        self.translator = TranslationService()
        self.categorizer = ArticleCategorizer()
        self._running = False
        self._parsing_in_progress = False
        # Kyrgyzstan timezone (UTC+6)
        self.kg_timezone = timezone(timedelta(hours=6))
        self.quiet_hours_start = 22  # 22:00 KG time
        self.quiet_hours_end = 10    # 10:00 KG time
    
    async def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        # Log quiet hours info
        kg_time = self.get_kg_time()
        is_quiet = self.is_quiet_hours()
        self.log_info(
            "Starting news scheduler",
            quiet_hours=f"{self.quiet_hours_start}:00 - {self.quiet_hours_end}:00 KG time",
            current_kg_time=kg_time.strftime("%H:%M:%S"),
            quiet_hours_active=is_quiet
        )
        print(f"[SCHEDULER] Quiet hours: {self.quiet_hours_start}:00 - {self.quiet_hours_end}:00 KG time", flush=True)
        print(f"[SCHEDULER] Current KG time: {kg_time.strftime('%H:%M:%S')} | Quiet hours active: {is_quiet}", flush=True)
        
        # Initialize database
        await db_manager.init()
        
        # Schedule periodic parsing
        self.scheduler.add_job(
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
            job_id="parse_news",
            interval_minutes=settings.parse_interval_minutes
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
        if self._parsing_in_progress:
            self.log_info("Parsing already in progress, skipping")
            print(f"[{datetime.utcnow().isoformat()}] Parsing already in progress, skipping", flush=True)
            return
        
        self._parsing_in_progress = True
        start_time = datetime.utcnow()
        
        try:
            # Add direct print for immediate visibility
            print(f"[{start_time.isoformat()}] Starting news parsing cycle", flush=True)
            
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
                        
                        # Categorize the article
                        category = self.categorizer.categorize(raw_article)
                        raw_article["category"] = category.value
                        
                        # Log categorization decision
                        self.log_info(
                            "Article categorized",
                            title=raw_article.get("title", "")[:50],
                            category=category.value,
                            source=raw_article.get("source")
                        )
                        
                        # Translate to Russian
                        translated_article = await self.translator.translate_article(raw_article)
                        
                        # Store Russian translations
                        translated_article["title_ru"] = translated_article.get("title")
                        translated_article["description_ru"] = translated_article.get("description")
                        translated_article["category"] = category.value  # Preserve category after translation
                        
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
                
                # Add direct print for immediate visibility
                print(f"[{datetime.utcnow().isoformat()}] Parsing cycle completed: {len(all_new_articles)} new articles", flush=True)
                
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
                        next_run = None
                        if hasattr(job, 'next_run_time'):
                            next_run = str(job.next_run_time)
                        self.log_info(
                            "Next parsing scheduled",
                            job_id=job.id,
                            next_run=next_run
                        )
                
                # Check if it's quiet hours before sending
                if self.is_quiet_hours():
                    self.log_info(
                        "Quiet hours active, postponing article sending",
                        kg_time=self.get_kg_time().strftime("%H:%M"),
                        articles_count=len(all_new_articles)
                    )
                    print(f"[QUIET HOURS] Not sending {len(all_new_articles)} articles (KG time: {self.get_kg_time().strftime('%H:%M')})", flush=True)
                    
                    # Mark articles as pending to send them later
                    for article in all_new_articles:
                        await article_repo.mark_as_pending(article.id)
                else:
                    # Send new articles to appropriate groups based on category
                    for article in all_new_articles:
                        # Determine target group based on category
                        target_group = "general"
                        if hasattr(article, 'category'):
                            if article.category == ArticleCategory.VULNERABILITIES.value:
                                # Only send to vulnerabilities group if it's configured
                                if settings.telegram_vulnerabilities_group_id:
                                    target_group = "vulnerabilities"
                                    self.log_info(
                                        "Sending vulnerability article",
                                        article_id=article.id,
                                        title=article.title[:50]
                                    )
                        
                        await self.bot.send_article_to_group(article, target_group)
                        # Small delay between articles
                        await asyncio.sleep(2)
                
                # Also check for pending articles from quiet hours
                if not self.is_quiet_hours():
                    pending_articles = await article_repo.get_pending_articles()
                    if pending_articles:
                        self.log_info(f"Sending {len(pending_articles)} pending articles from quiet hours")
                        for article in pending_articles:
                            # Determine target group based on category for pending articles too
                            target_group = "general"
                            if hasattr(article, 'category'):
                                if article.category == ArticleCategory.VULNERABILITIES.value:
                                    if settings.telegram_vulnerabilities_group_id:
                                        target_group = "vulnerabilities"
                            
                            await self.bot.send_article_to_group(article, target_group)
                            await asyncio.sleep(2)
                    
        except Exception as e:
            print(f"[{datetime.utcnow().isoformat()}] ERROR in parsing cycle: {str(e)}", flush=True)
            self.log_error("Error in parsing cycle", error=str(e))
            self.increment_counter(ARTICLES_PARSED, {"status": "error"})
            
            # Notify admin about error
            await self.bot.send_admin_notification(
                f"❌ Ошибка парсинга:\n{str(e)[:200]}"
            )
        finally:
            self._parsing_in_progress = False
    
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
    
    def get_kg_time(self) -> datetime:
        """Get current time in Kyrgyzstan timezone."""
        return datetime.now(self.kg_timezone)
    
    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours (22:00-10:00 KG time)."""
        kg_time = self.get_kg_time()
        current_hour = kg_time.hour
        
        # Quiet hours: from 22:00 to 10:00 (crosses midnight)
        if self.quiet_hours_start > self.quiet_hours_end:
            # Hours cross midnight (e.g., 22:00 to 10:00)
            return current_hour >= self.quiet_hours_start or current_hour < self.quiet_hours_end
        else:
            # Hours don't cross midnight
            return self.quiet_hours_start <= current_hour < self.quiet_hours_end
    
    async def keep_alive(self):
        """Send keep-alive ping to prevent Render from sleeping."""
        try:
            # Log scheduler state
            jobs = self.scheduler.get_jobs() if self.scheduler else []
            jobs_info = []
            for j in jobs:
                job_info = {"id": j.id}
                if hasattr(j, 'next_run_time'):
                    job_info["next_run"] = str(j.next_run_time)
                jobs_info.append(job_info)
            
            # Add current KG time and quiet hours status
            kg_time = self.get_kg_time()
            quiet_hours = self.is_quiet_hours()
            
            # Add direct print for immediate visibility
            print(f"[{datetime.utcnow().isoformat()}] Keep-alive: {len(jobs)} jobs scheduled | KG time: {kg_time.strftime('%H:%M')} | Quiet: {quiet_hours}", flush=True)
            
            self.log_info(
                "Keep-alive: Scheduler state",
                running=self.scheduler.running if self.scheduler else False,
                jobs_count=len(jobs),
                jobs_info=jobs_info,
                kg_time=kg_time.strftime("%H:%M:%S"),
                quiet_hours_active=quiet_hours
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