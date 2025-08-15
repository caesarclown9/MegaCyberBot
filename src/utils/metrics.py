from typing import Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
import asyncio
from src.config import settings


# Metrics definitions
ARTICLES_PARSED = Counter(
    "articles_parsed_total",
    "Total number of articles parsed",
    ["status"]
)

TRANSLATION_REQUESTS = Counter(
    "translation_requests_total",
    "Total number of translation requests",
    ["service", "status"]
)

TELEGRAM_MESSAGES = Counter(
    "telegram_messages_sent_total",
    "Total number of Telegram messages sent",
    ["type", "status", "group"]
)

PARSER_DURATION = Histogram(
    "parser_duration_seconds",
    "Time spent parsing articles",
    ["source"]
)

TRANSLATION_DURATION = Histogram(
    "translation_duration_seconds",
    "Time spent translating text",
    ["service"]
)

ACTIVE_USERS = Gauge(
    "active_users_total",
    "Total number of active bot users"
)

BOT_INFO = Info(
    "bot_info",
    "Bot information"
)


def track_time(metric: Histogram, **labels: str):
    """Decorator to track execution time of functions."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                metric.labels(**labels).observe(time.time() - start)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                metric.labels(**labels).observe(time.time() - start)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def init_metrics() -> None:
    """Initialize metrics with default values."""
    if settings.enable_metrics:
        BOT_INFO.info({
            "version": "1.0.0",
            "environment": settings.environment
        })


class MetricsMixin:
    """Mixin class to add metrics capabilities to any class."""
    
    def increment_counter(
        self,
        counter: Counter,
        labels: Optional[Dict[str, str]] = None,
        value: int = 1
    ) -> None:
        if settings.enable_metrics:
            if labels:
                counter.labels(**labels).inc(value)
            else:
                counter.inc(value)
    
    def set_gauge(
        self,
        gauge: Gauge,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        if settings.enable_metrics:
            if labels:
                gauge.labels(**labels).set(value)
            else:
                gauge.set(value)