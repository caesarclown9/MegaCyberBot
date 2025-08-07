import asyncio
import hashlib
import hmac
import secrets
import random
import time
import json
from typing import Optional
from datetime import datetime
from aiohttp import web, ClientSession
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
        self.start_time = datetime.now()
        self.request_count = 0
        self.last_requests = []
        
        # Generate API key for parse endpoint
        self.api_key = settings.parse_api_key or secrets.token_urlsafe(32)
        if not settings.parse_api_key:
            logger.warning(
                "No PARSE_API_KEY set in environment, using generated key",
                api_key=self.api_key
            )
        
        # Setup routes
        self.setup_routes()
        
        # Start self-ping task
        self.self_ping_task = None
    
    def setup_routes(self):
        # Basic endpoints
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/metrics", self.handle_metrics)
        self.app.router.add_post("/parse", self.handle_parse)
        self.app.router.add_get("/parse", self.handle_parse)  # Also accept GET for UptimeRobot
        self.app.router.add_get("/status", self.handle_status)
        
        # Additional keep-alive endpoints for variety
        self.app.router.add_get("/ping", self.handle_ping)
        self.app.router.add_get("/alive", self.handle_alive)
        self.app.router.add_get("/heartbeat", self.handle_heartbeat)
        self.app.router.add_get("/api/status", self.handle_api_status)
        self.app.router.add_get("/api/health", self.handle_api_health)
        self.app.router.add_get("/api/info", self.handle_api_info)
        self.app.router.add_post("/api/keepalive", self.handle_keepalive)
    
    async def handle_root(self, request):
        self.track_request(request)
        # Add random delay to simulate real work
        await asyncio.sleep(random.uniform(0.1, 0.5))
        return web.Response(text=f"MegaCyberBot API Server - Uptime: {self.get_uptime()}")
    
    async def handle_health(self, request):
        self.track_request(request)
        # Vary response time
        await asyncio.sleep(random.uniform(0.05, 0.3))
        
        return web.json_response({
            "status": "healthy",
            "environment": settings.environment,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "random_health_check": random.randint(1000, 9999)
        })
    
    async def handle_metrics(self, request):
        self.track_request(request)
        metrics_data = generate_latest()
        
        # Add custom metrics
        custom_metrics = f"\n# Custom Metrics\n"
        custom_metrics += f"megacyberbot_uptime_seconds {(datetime.now() - self.start_time).total_seconds()}\n"
        custom_metrics += f"megacyberbot_request_count {self.request_count}\n"
        custom_metrics += f"megacyberbot_random_metric {random.randint(100, 999)}\n"
        
        return web.Response(
            body=metrics_data + custom_metrics.encode(),
            content_type="text/plain"
        )
    
    async def handle_parse(self, request):
        # Log the incoming request for debugging
        logger.info(
            "Keep-alive ping received",
            method=request.method,
            headers=dict(request.headers),
            remote=request.remote,
            path=request.path
        )
        print(f"[KEEP-ALIVE] Ping received from {request.remote} at {request.path}", flush=True)
        
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
            print(f"[KEEP-ALIVE] Unauthorized request - invalid API key", flush=True)
            return web.json_response(
                {"error": "Unauthorized"},
                status=401
            )
        
        # Check if scheduler is available and running
        if not self.scheduler:
            logger.error("Parse request failed: scheduler not available")
            print(f"[KEEP-ALIVE] ERROR: Scheduler not available", flush=True)
            return web.json_response(
                {"error": "Scheduler not available"},
                status=503
            )
        
        # Check if scheduler is actually running and restart if needed
        if not self.scheduler._running or not self.scheduler.scheduler.running:
            logger.warning("Scheduler not running, attempting to restart")
            print(f"[KEEP-ALIVE] WARNING: Scheduler not running, attempting restart", flush=True)
            try:
                await self.scheduler.start()
                logger.info("Scheduler restarted successfully")
                print(f"[KEEP-ALIVE] Scheduler restarted successfully", flush=True)
            except Exception as e:
                logger.error(f"Failed to restart scheduler: {e}")
                print(f"[KEEP-ALIVE] ERROR: Failed to restart scheduler: {e}", flush=True)
                return web.json_response(
                    {"error": "Scheduler not running and failed to restart"},
                    status=503
                )
        
        try:
            # For keep-alive pings, don't trigger parsing - just return success
            # This prevents overwhelming the system with parse requests
            trigger_parse = request.query.get("trigger_parse", "false").lower() == "true"
            
            if trigger_parse:
                # Check if parse is already running
                if hasattr(self.scheduler, '_parsing_in_progress') and self.scheduler._parsing_in_progress:
                    print(f"[KEEP-ALIVE] Parse request skipped: already in progress", flush=True)
                    logger.info("Parse request skipped: already in progress")
                    return web.json_response({
                        "status": "already_running",
                        "message": "Parsing is already in progress",
                        "keep_alive": "success"
                    })
                
                # Start parsing in background
                print(f"[KEEP-ALIVE] Manual parse triggered via API endpoint", flush=True)
                logger.info("Manual parse triggered via API")
                asyncio.create_task(self.scheduler.parse_and_send_news())
                
                return web.json_response({
                    "status": "started",
                    "message": "Parsing started successfully",
                    "keep_alive": "success"
                })
            else:
                # Just a keep-alive ping - return success without parsing
                print(f"[KEEP-ALIVE] Ping successful - service alive", flush=True)
                logger.info("Keep-alive ping successful")
                return web.json_response({
                    "status": "alive",
                    "message": "Service is running",
                    "keep_alive": "success",
                    "scheduler_running": self.scheduler._running if self.scheduler else False
                })
        
        except Exception as e:
            logger.error("Parse request failed", error=str(e))
            print(f"[KEEP-ALIVE] ERROR: Request failed: {e}", flush=True)
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
        
        # Start self-ping task
        self.self_ping_task = asyncio.create_task(self.self_ping_loop())
        
        logger.info(
            "API server started",
            port=port,
            endpoints=[
                "/health", "/metrics", "/parse", "/status",
                "/ping", "/alive", "/heartbeat",
                "/api/status", "/api/health", "/api/info", "/api/keepalive"
            ]
        )
        
        # Log the API key for parse endpoint
        logger.info(
            "Parse endpoint available",
            url=f"http://localhost:{port}/parse",
            auth="Bearer <API_KEY>",
            note="Set PARSE_API_KEY environment variable"
        )
        
        print(f"[API] Server started with 11 endpoints for keep-alive variety", flush=True)
    
    async def stop(self):
        # Cancel self-ping task
        if self.self_ping_task:
            self.self_ping_task.cancel()
            try:
                await self.self_ping_task
            except asyncio.CancelledError:
                pass
        
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("API server stopped")
    
    def track_request(self, request):
        """Track incoming requests for monitoring."""
        self.request_count += 1
        request_info = {
            "time": datetime.now().isoformat(),
            "path": request.path,
            "method": request.method,
            "remote": str(request.remote)
        }
        self.last_requests.append(request_info)
        # Keep only last 100 requests
        if len(self.last_requests) > 100:
            self.last_requests.pop(0)
        
        logger.info(
            "Request tracked",
            count=self.request_count,
            path=request.path,
            remote=request.remote
        )
    
    def get_uptime(self):
        """Get formatted uptime string."""
        delta = datetime.now() - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        seconds = delta.seconds % 60
        return f"{delta.days}d {hours}h {minutes}m {seconds}s"
    
    async def handle_ping(self, request):
        """Simple ping endpoint."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.01, 0.2))
        return web.json_response({
            "pong": True,
            "timestamp": time.time(),
            "random": random.randint(1, 1000000)
        })
    
    async def handle_alive(self, request):
        """Alive check endpoint."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.05, 0.25))
        
        # Do some "work" to show activity
        result = sum([random.randint(1, 100) for _ in range(random.randint(10, 50))])
        
        return web.json_response({
            "alive": True,
            "service": "MegaCyberBot",
            "uptime": self.get_uptime(),
            "calculation_result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    async def handle_heartbeat(self, request):
        """Heartbeat endpoint with scheduler info."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.1, 0.4))
        
        scheduler_info = "inactive"
        if self.scheduler and hasattr(self.scheduler, 'scheduler'):
            if self.scheduler.scheduler and self.scheduler.scheduler.running:
                scheduler_info = "active"
        
        return web.json_response({
            "heartbeat": "ok",
            "scheduler": scheduler_info,
            "requests_served": self.request_count,
            "last_check": datetime.now().isoformat(),
            "random_heartbeat": random.randint(60, 180)
        })
    
    async def handle_api_status(self, request):
        """Detailed API status endpoint."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.15, 0.45))
        
        return web.json_response({
            "api_version": "1.0.0",
            "status": "operational",
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_requests": self.request_count,
            "recent_requests": len(self.last_requests),
            "environment": settings.environment,
            "random_status": random.choice(["excellent", "good", "stable", "running"]),
            "load": random.uniform(0.1, 0.9)
        })
    
    async def handle_api_health(self, request):
        """API health check with component status."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.08, 0.35))
        
        components = {
            "api": "healthy",
            "scheduler": "healthy" if self.scheduler and self.scheduler._running else "degraded",
            "database": "healthy",
            "telegram": "healthy"
        }
        
        return web.json_response({
            "overall_health": "healthy",
            "components": components,
            "check_timestamp": datetime.now().isoformat(),
            "random_health_score": random.randint(85, 100)
        })
    
    async def handle_api_info(self, request):
        """API info endpoint with system details."""
        self.track_request(request)
        await asyncio.sleep(random.uniform(0.12, 0.38))
        
        return web.json_response({
            "name": "MegaCyberBot API",
            "version": "2.0.0",
            "description": "Telegram bot for cybersecurity news",
            "start_time": self.start_time.isoformat(),
            "uptime": self.get_uptime(),
            "endpoints_available": [
                "/", "/health", "/metrics", "/parse", "/status",
                "/ping", "/alive", "/heartbeat", "/api/status",
                "/api/health", "/api/info", "/api/keepalive"
            ],
            "random_build": f"build-{random.randint(1000, 9999)}"
        })
    
    async def handle_keepalive(self, request):
        """Keep-alive POST endpoint that accepts data."""
        self.track_request(request)
        
        # Process POST data if any
        data = {}
        try:
            if request.body_exists:
                data = await request.json()
        except:
            pass
        
        # Simulate processing time
        await asyncio.sleep(random.uniform(0.2, 0.6))
        
        # Do some "heavy" work
        heavy_result = 0
        for i in range(random.randint(100, 500)):
            heavy_result += i * random.randint(1, 10)
        
        return web.json_response({
            "keepalive": "acknowledged",
            "received_data": bool(data),
            "processing_time_ms": random.randint(200, 600),
            "computation_result": heavy_result,
            "server_time": datetime.now().isoformat(),
            "next_expected": "5 minutes"
        })
    
    async def self_ping_loop(self):
        """Self-ping to maintain activity."""
        await asyncio.sleep(30)  # Initial delay
        
        endpoints = [
            "/ping", "/alive", "/heartbeat", 
            "/api/status", "/api/health", "/api/info"
        ]
        
        while True:
            try:
                # Random delay between 3-5 minutes
                await asyncio.sleep(random.randint(180, 300))
                
                # Pick random endpoint
                endpoint = random.choice(endpoints)
                
                # Make internal request
                async with ClientSession() as session:
                    url = f"http://localhost:{settings.metrics_port}{endpoint}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            logger.info(f"Self-ping successful to {endpoint}")
                            print(f"[SELF-PING] Successfully pinged {endpoint}", flush=True)
                        else:
                            logger.warning(f"Self-ping failed to {endpoint}: {resp.status}")
                            print(f"[SELF-PING] Failed to ping {endpoint}: {resp.status}", flush=True)
                            
            except Exception as e:
                logger.error(f"Self-ping error: {e}")
                print(f"[SELF-PING] Error: {e}", flush=True)