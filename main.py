import asyncio
import signal
import sys
from typing import Optional
from src.config import settings
from src.utils import setup_logging, get_logger, init_metrics
from src.bot import TelegramBot, NewsScheduler
from src.api import APIServer

logger = get_logger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self):
        self.bot: Optional[TelegramBot] = None
        self.scheduler: Optional[NewsScheduler] = None
        self.api_server: Optional[APIServer] = None
        self._running = False
    
    async def start(self):
        """Start the application."""
        try:
            # Setup logging
            setup_logging()
            print(f"[STARTUP] Starting HackerNews Telegram Bot - Environment: {settings.environment}", flush=True)
            logger.info("Starting HackerNews Telegram Bot", environment=settings.environment)
            
            # Initialize metrics
            init_metrics()
            
            # Initialize bot
            self.bot = TelegramBot()
            
            # Initialize scheduler
            self.scheduler = NewsScheduler(self.bot)
            
            # Initialize and start API server
            if settings.enable_metrics:
                self.api_server = APIServer(scheduler=self.scheduler)
                await self.api_server.start(port=settings.metrics_port)
                logger.info("API server started with metrics", port=settings.metrics_port)
            
            # Start scheduler (runs in background)
            await self.scheduler.start()
            
            # Mark as running
            self._running = True
            
            # Create tasks for bot and keep-alive
            bot_task = asyncio.create_task(self.bot.start())
            keep_alive_task = asyncio.create_task(self.keep_alive())
            
            # Wait for both tasks (they should run forever)
            await asyncio.gather(bot_task, keep_alive_task)
            
        except Exception as e:
            logger.error("Failed to start application", error=str(e))
            await self.shutdown()
            raise
    
    async def keep_alive(self):
        """Keep the application alive and monitor scheduler."""
        while self._running:
            await asyncio.sleep(60)  # Check every minute
            
            # Log scheduler status
            if self.scheduler and self.scheduler.scheduler:
                jobs = self.scheduler.scheduler.get_jobs()
                jobs_info = []
                for job in jobs:
                    job_info = {"id": job.id}
                    if hasattr(job, 'next_run_time'):
                        job_info["next_run"] = str(job.next_run_time)
                    jobs_info.append(job_info)
                
                logger.info(
                    "Scheduler status check",
                    running=self.scheduler.scheduler.running,
                    jobs_count=len(jobs),
                    jobs=jobs_info
                )
            
            # Ensure scheduler is still running
            if self.scheduler and not self.scheduler._running:
                logger.warning("Scheduler stopped unexpectedly, restarting...")
                await self.scheduler.start()
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        if not self._running:
            return
        
        logger.info("Shutting down application")
        self._running = False
        
        try:
            # Stop bot
            if self.bot:
                await self.bot.stop()
            
            # Stop scheduler
            if self.scheduler:
                await self.scheduler.stop()
            
            # Stop API server
            if self.api_server:
                await self.api_server.stop()
            
            logger.info("Application shutdown complete")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


async def main():
    """Main entry point."""
    app = Application()
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("Received signal", signal=sig)
        asyncio.create_task(app.shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Application error", error=str(e))
        raise
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Force unbuffered output
    import os
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    print(f"[INIT] Starting application...", flush=True)
    # Run the application
    asyncio.run(main())