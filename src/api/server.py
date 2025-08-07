import asyncio
import hashlib
import hmac
import secrets
from typing import Optional
from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)


class APIServer:
    def __init__(self, scheduler=None):
        self.app = web.Application()
        self.scheduler = scheduler
        self.runner = None
        self.site = None
        
        # Generate API key for parse endpoint
        self.api_key = settings.parse_api_key or secrets.token_urlsafe(32)
        if not settings.parse_api_key:
            logger.warning(
                "No PARSE_API_KEY set in environment, using generated key",
                api_key=self.api_key
            )
        
        # Setup routes
        self.setup_routes()
    
    def setup_routes(self):
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/metrics", self.handle_metrics)
        self.app.router.add_post("/parse", self.handle_parse)
        self.app.router.add_get("/parse", self.handle_parse)  # Also accept GET for UptimeRobot
        self.app.router.add_get("/status", self.handle_status)
    
    async def handle_root(self, request):
        return web.Response(text="MegaCyberBot API Server")
    
    async def handle_health(self, request):
        return web.json_response({
            "status": "healthy",
            "environment": settings.environment
        })
    
    async def handle_metrics(self, request):
        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            content_type=CONTENT_TYPE_LATEST
        )
    
    async def handle_parse(self, request):
        # Check authentication - support both header and query param for UptimeRobot
        provided_key = None
        
        # First check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]  # Remove "Bearer " prefix
        
        # If no header, check query parameter (for UptimeRobot GET requests)
        if not provided_key:
            provided_key = request.query.get("key", "")
        
        if not provided_key or not secrets.compare_digest(provided_key, self.api_key):
            logger.warning("Unauthorized parse request: invalid or missing API key")
            return web.json_response(
                {"error": "Unauthorized"},
                status=401
            )
        
        # Check if scheduler is available and running
        if not self.scheduler:
            logger.error("Parse request failed: scheduler not available")
            return web.json_response(
                {"error": "Scheduler not available"},
                status=503
            )
        
        # Check if scheduler is actually running and restart if needed
        if not self.scheduler._running or not self.scheduler.scheduler.running:
            logger.warning("Scheduler not running, attempting to restart")
            try:
                await self.scheduler.start()
                logger.info("Scheduler restarted successfully")
            except Exception as e:
                logger.error(f"Failed to restart scheduler: {e}")
                return web.json_response(
                    {"error": "Scheduler not running and failed to restart"},
                    status=503
                )
        
        try:
            # Check if parse is already running
            if hasattr(self.scheduler, '_parsing_in_progress') and self.scheduler._parsing_in_progress:
                print(f"[API] Parse request skipped: already in progress", flush=True)
                logger.info("Parse request skipped: already in progress")
                return web.json_response({
                    "status": "already_running",
                    "message": "Parsing is already in progress"
                })
            
            # Start parsing in background
            print(f"[API] Manual parse triggered via API endpoint", flush=True)
            logger.info("Manual parse triggered via API")
            asyncio.create_task(self.scheduler.parse_and_send_news())
            
            return web.json_response({
                "status": "started",
                "message": "Parsing started successfully"
            })
        
        except Exception as e:
            logger.error("Parse request failed", error=str(e))
            return web.json_response(
                {"error": "Internal server error"},
                status=500
            )
    
    async def handle_status(self, request):
        status_data = {
            "scheduler": {
                "available": self.scheduler is not None,
                "running": False,
                "jobs": []
            }
        }
        
        if self.scheduler and hasattr(self.scheduler, 'scheduler'):
            scheduler_obj = self.scheduler.scheduler
            if scheduler_obj:
                status_data["scheduler"]["running"] = scheduler_obj.running
                
                jobs = scheduler_obj.get_jobs()
                for job in jobs:
                    job_info = {"id": job.id}
                    if hasattr(job, 'next_run_time'):
                        job_info["next_run"] = str(job.next_run_time)
                    status_data["scheduler"]["jobs"].append(job_info)
        
        return web.json_response(status_data)
    
    async def start(self, port: int = 8000):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(
            self.runner,
            "0.0.0.0",
            port
        )
        
        await self.site.start()
        
        logger.info(
            "API server started",
            port=port,
            endpoints=["/health", "/metrics", "/parse", "/status"]
        )
        
        # Log the API key for parse endpoint
        logger.info(
            "Parse endpoint available",
            url=f"http://localhost:{port}/parse",
            auth="Bearer <API_KEY>",
            note="Set PARSE_API_KEY environment variable"
        )
    
    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("API server stopped")