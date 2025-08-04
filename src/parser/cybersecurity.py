from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from src.utils import track_time, PARSER_DURATION
from src.config import settings
from .base import BaseParser


class CybersecurityNewsParser(BaseParser):
    """Parser for various cybersecurity news websites."""
    
    # Multiple sources to try
    SOURCES = [
        {
            "name": "BleepingComputer",
            "url": "https://www.bleepingcomputer.com/",
            "selector": "article.bc_latest_news_text"
        },
        {
            "name": "SecurityWeek", 
            "url": "https://www.securityweek.com/",
            "selector": "div.post"
        },
        {
            "name": "InfoSecurity Magazine",
            "url": "https://www.infosecurity-magazine.com/",
            "selector": "article"
        }
    ]
    
    @track_time(PARSER_DURATION, source="cybersecurity_news")
    async def parse_articles(self, url: str = None) -> List[Dict[str, Any]]:
        """Parse articles from available cybersecurity sources."""
        all_articles = []
        
        for source in self.SOURCES:
            try:
                self.log_info(f"Trying source: {source['name']}")
                
                # Try to fetch from this source
                html = await self.fetch_page(source["url"])
                soup = self.parse_html(html)
                
                # Find articles
                articles = self._parse_source_articles(soup, source)
                if articles:
                    self.log_info(f"Found {len(articles)} articles from {source['name']}")
                    all_articles.extend(articles)
                    break  # Use first working source
                    
            except Exception as e:
                self.log_warning(f"Failed to parse {source['name']}", error=str(e))
                continue
        
        # Filter and sort articles
        if all_articles:
            # Filter by date
            filtered_articles = []
            for article in all_articles:
                article_date = article.get("published_at")
                if article_date and article_date >= settings.min_article_datetime:
                    filtered_articles.append(article)
            
            # Sort by date, newest first
            filtered_articles.sort(key=lambda x: x.get("published_at", datetime.utcnow()), reverse=True)
            
            # Limit results
            final_articles = filtered_articles[:settings.max_articles_per_fetch]
            
            self.log_info("Parsed articles from cybersecurity sources", count=len(final_articles))
            return final_articles
        
        self.log_warning("No articles found from any source")
        return []
    
    def _parse_source_articles(self, soup: BeautifulSoup, source: Dict) -> List[Dict[str, Any]]:
        """Parse articles from a specific source."""
        articles = []
        
        try:
            # Find article containers
            containers = soup.select(source["selector"])[:10]  # Limit to first 10
            
            for container in containers:
                article_data = self._extract_generic_article(container, source)
                if article_data:
                    articles.append(article_data)
                    
        except Exception as e:
            self.log_warning(f"Failed to parse {source['name']} articles", error=str(e))
        
        return articles
    
    def _extract_generic_article(self, container: Tag, source: Dict) -> Optional[Dict[str, Any]]:
        """Extract article data from container."""
        try:
            # Find link
            link_elem = container.find("a")
            if not link_elem or not link_elem.get("href"):
                return None
            
            url = link_elem["href"]
            if not url.startswith("http"):
                url = urljoin(source["url"], url)
            
            # Find title
            title_elem = (
                container.find("h1") or
                container.find("h2") or
                container.find("h3") or
                link_elem
            )
            
            if not title_elem:
                return None
                
            title = self.clean_text(title_elem.get_text())
            if not title or len(title) < 10:
                return None
            
            # Find description
            description = None
            desc_elem = container.find("p")
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())
                if description and len(description) > 300:
                    description = description[:297] + "..."
            
            # Set published date to now (we can't reliably extract dates from all sources)
            published_at = datetime.utcnow()
            
            return {
                "title": title,
                "url": url,
                "description": description,
                "published_at": published_at,
                "source": source["name"]
            }
            
        except Exception as e:
            self.log_warning("Failed to extract article data", error=str(e))
            return None
    
    def extract_article_data(self, element: Tag) -> Optional[Dict[str, Any]]:
        """Extract data from an article element (compatibility method)."""
        return self._extract_generic_article(element, {"name": "Generic", "url": ""})