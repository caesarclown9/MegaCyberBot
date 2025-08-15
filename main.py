import asyncio
import signal
import sys
from typing import Optional
from src.config import settings
from src.utils import setup_logging, get_logger, init_metrics
from src.bot import TelegramBot, NewsScheduler
from src.api import APIServer
from src.database import db_manager, DatabaseMigrator

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
            
            # Run database migrations automatically
            logger.info("Running database migrations...")
            print("[STARTUP] Checking database migrations...", flush=True)
            try:
                await db_manager.init()
                async with db_manager.get_session() as session:
                    migrator = DatabaseMigrator()
                    await migrator.run_migrations(session)
                    await session.commit()
                print("[STARTUP] Database migrations completed", flush=True)
            except Exception as e:
                logger.warning(f"Migration check completed with warning: {e}")
                print(f"[STARTUP] Migration check completed (non-critical): {e}", flush=True)
                # Continue anyway - migrations might already be applied
            
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
        import aiohttp
        import random
        from datetime import datetime
        
        consecutive_failures = 0
        max_consecutive_failures = 3
        check_interval = 30  # Check every 30 seconds
        
        # Wait a bit before starting
        await asyncio.sleep(10)
        
        while self._running:
            try:
                await asyncio.sleep(check_interval)
                
                # Print heartbeat to stdout to show we're alive
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"[HEARTBEAT {current_time}] Application alive - running={self._running}", flush=True)
                
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
                    print(f"[HEARTBEAT {current_time}] Scheduler: running={self.scheduler.scheduler.running}, jobs={len(jobs)}", flush=True)
                
                # Ensure scheduler is still running
                if self.scheduler and not self.scheduler._running:
                    logger.warning("Scheduler stopped unexpectedly, restarting...")
                    print(f"[HEARTBEAT {current_time}] WARNING: Scheduler stopped, attempting restart", flush=True)
                    try:
                        await self.scheduler.start()
                        consecutive_failures = 0
                        print(f"[HEARTBEAT {current_time}] Scheduler restarted successfully", flush=True)
                    except Exception as e:
                        consecutive_failures += 1
                        logger.error(f"Failed to restart scheduler (attempt {consecutive_failures}/{max_consecutive_failures}): {e}")
                        print(f"[HEARTBEAT {current_time}] ERROR: Failed to restart scheduler: {e}", flush=True)
                        
                        if consecutive_failures >= max_consecutive_failures:
                            logger.critical("Too many scheduler restart failures, shutting down")
                            print(f"[HEARTBEAT {current_time}] CRITICAL: Too many failures, shutting down", flush=True)
                            self._running = False
                            break
                else:
                    consecutive_failures = 0
                
                # Every few heartbeats, make an external self-ping to generate traffic
                if random.random() < 0.3:  # 30% chance
                    try:
                        async with aiohttp.ClientSession() as session:
                            endpoints = ["/ping", "/alive", "/heartbeat", "/api/status"]
                            endpoint = random.choice(endpoints)
                            url = f"http://localhost:{settings.metrics_port}{endpoint}"
                            
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                if resp.status == 200:
                                    print(f"[HEARTBEAT {current_time}] External self-ping to {endpoint} successful", flush=True)
                                else:
                                    print(f"[HEARTBEAT {current_time}] External self-ping to {endpoint} failed: {resp.status}", flush=True)
                    except Exception as e:
                        print(f"[HEARTBEAT {current_time}] External self-ping error: {e}", flush=True)
                        
            except Exception as e:
                logger.error(f"Error in keep_alive loop: {e}")
                print(f"[HEARTBEAT] ERROR in loop: {e}", flush=True)
    
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
        print(f"[SHUTDOWN] Received signal {sig}, shutting down gracefully", flush=True)
        asyncio.create_task(app.shutdown())
        # Don't call sys.exit immediately - let the async shutdown complete
    
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
    
    print(f"[INIT] Starting MegaCyberBot application...", flush=True)
    print(f"[INIT] Keep-alive strategy: Multiple endpoints, self-ping, heartbeat every 30s", flush=True)
    print(f"[INIT] External monitoring should ping every 5 minutes to various endpoints", flush=True)
    
    # Run the application
    asyncio.run(main())