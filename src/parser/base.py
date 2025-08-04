from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from src.utils import LoggerMixin, MetricsMixin, track_time, PARSER_DURATION
from src.config import settings


class BaseParser(ABC, LoggerMixin, MetricsMixin):
    """Abstract base class for content parsers."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
        self.timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
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
            
            # Create connector
            connector = aiohttp.TCPConnector(**connector_kwargs) if connector_kwargs else None
            
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
    
    async def fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL."""
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            self.log_error("Failed to fetch page", url=url, error=str(e))
            raise
    
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