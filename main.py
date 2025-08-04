import asyncio
import signal
import sys
from typing import Optional
from prometheus_client import start_http_server
from src.config import settings
from src.utils import setup_logging, get_logger, init_metrics
from src.bot import TelegramBot, NewsScheduler

logger = get_logger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self):
        self.bot: Optional[TelegramBot] = None
        self.scheduler: Optional[NewsScheduler] = None
        self._running = False
    
    async def start(self):
        """Start the application."""
        try:
            # Setup logging
            setup_logging()
            logger.info("Starting HackerNews Telegram Bot", environment=settings.environment)
            
            # Initialize metrics
            init_metrics()
            
            # Start metrics server
            if settings.enable_metrics:
                start_http_server(settings.metrics_port)
                logger.info("Metrics server started", port=settings.metrics_port)
            
            # Initialize bot
            self.bot = TelegramBot()
            
            # Initialize scheduler
            self.scheduler = NewsScheduler(self.bot)
            
            # Start scheduler
            await self.scheduler.start()
            
            # Start bot
            self._running = True
            await self.bot.start()
            
        except Exception as e:
            logger.error("Failed to start application", error=str(e))
            await self.shutdown()
            raise
    
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
    # Run the application
    asyncio.run(main())