from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
import asyncio
import random
import os
from bs4 import BeautifulSoup
from src.utils import LoggerMixin, MetricsMixin, track_time, PARSER_DURATION
from src.config import settings


class BaseParser(ABC, LoggerMixin, MetricsMixin):
    """Abstract base class for content parsers."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
        self.timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        # User agent rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]
        self.headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    
    async def __aenter__(self):
        if self._own_session:
            # Setup proxy if configured
            connector_kwargs = {}
            if settings.proxy_url:
                connector_kwargs['trust_env'] = True
            
            # Create connector with SSL settings
            connector = aiohttp.TCPConnector(
                ssl=False,  # Disable SSL verification for problematic sites
                limit=100,
                limit_per_host=30,
                force_close=True,  # Force close connections
                enable_cleanup_closed=True,  # Clean up closed connections
                **connector_kwargs
            )
            
            # Session kwargs
            session_kwargs = {
                'timeout': self.timeout,
                'headers': self.headers
            }
            
            if connector:
                session_kwargs['connector'] = connector
            
            # Add proxy to session if configured
            if settings.proxy_url:
                session_kwargs['trust_env'] = True
            
            self.session = aiohttp.ClientSession(**session_kwargs)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str, max_retries: int = 3) -> str:
        """Fetch HTML content from URL with retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Rotate user agent for each attempt
                headers = self.headers.copy()
                headers["User-Agent"] = random.choice(self.user_agents)
                
                # Add delay between retries
                if attempt > 0:
                    delay = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                    self.log_info(f"Retry attempt {attempt + 1}/{max_retries} after {delay}s delay", url=url)
                    await asyncio.sleep(delay)
                
                self.log_debug("Fetching page", url=url, attempt=attempt + 1)
                
                # Use proxy configuration
                proxy = None
                if settings.proxy_url:
                    proxy = settings.proxy_url
                elif os.getenv('HTTP_PROXY'):
                    proxy = os.getenv('HTTP_PROXY')
                elif os.getenv('HTTPS_PROXY'):
                    proxy = os.getenv('HTTPS_PROXY')
                
                async with self.session.get(
                    url,
                    headers=headers,
                    proxy=proxy,
                    ssl=False,  # Disable SSL verification for problematic sites
                    allow_redirects=True,
                    max_redirects=5
                ) as response:
                    self.log_debug("Response received", url=url, status=response.status)
                    
                    if response.status == 0:
                        # Connection error, retry
                        raise aiohttp.ClientConnectionError("Connection failed (status 0)")
                    
                    response.raise_for_status()
                    return await response.text()
                    
            except aiohttp.ClientResponseError as e:
                last_error = e
                self.log_warning(f"HTTP error on attempt {attempt + 1}", url=url, status=e.status, error_message=e.message)
                if e.status in [429, 503]:  # Rate limiting or service unavailable
                    continue
                elif e.status >= 400 and e.status < 500:
                    # Client error, no point retrying
                    raise
            except (aiohttp.ClientError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                last_error = e
                self.log_warning(f"Connection error on attempt {attempt + 1}", url=url, error=str(e), error_type=type(e).__name__)
                continue
            except Exception as e:
                last_error = e
                self.log_warning(f"Unexpected error on attempt {attempt + 1}", url=url, error=str(e))
                continue
        
        # All retries failed
        self.log_error(f"Failed to fetch page after {max_retries} attempts", url=url, error=str(last_error))
        raise last_error if last_error else Exception(f"Failed to fetch {url}")
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "lxml")
    
    @abstractmethod
    async def parse_articles(self, url: str) -> List[Dict[str, Any]]:
        """Parse articles from the given URL."""
        pass
    
    @abstractmethod
    def extract_article_data(self, element: Any) -> Optional[Dict[str, Any]]:
        """Extract data from a single article element."""
        pass
    
    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean and normalize text."""
        if not text:
            return None
        
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text if text else None
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_str:
            return None
        
        # Clean the date string
        date_str = date_str.strip()
        
        # Common date formats to try
        date_formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%B %d, %Y",
            "%b %d, %Y", 
            "%d %B %Y",
            "%d %b %Y",
            "%b %d %Y",  # Aug 02 2025
            "%B %d %Y",  # August 02 2025
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Ensure naive datetime for comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except ValueError:
                continue
        
        self.log_warning("Failed to parse date", date_str=date_str)
        return None