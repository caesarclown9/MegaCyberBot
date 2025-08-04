from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import asyncio
import feedparser
from urllib.parse import urljoin
from src.utils import track_time, PARSER_DURATION
from src.config import settings
from .base import BaseParser


class RSSFeedParser(BaseParser):
    """Parser for RSS feeds from cybersecurity websites."""
    
    # RSS feeds that are often accessible even when main sites are blocked
    RSS_FEEDS = [
        {
            "name": "Krebs on Security",
            "url": "https://krebsonsecurity.com/feed/",
            "source": "KrebsOnSecurity"
        },
        {
            "name": "Dark Reading",
            "url": "https://www.darkreading.com/rss.xml",
            "source": "DarkReading"
        },
        {
            "name": "Threatpost",
            "url": "https://threatpost.com/feed/",
            "source": "Threatpost"
        },
        {
            "name": "CSO Online",
            "url": "https://www.csoonline.com/index.rss",
            "source": "CSOOnline"
        },
        {
            "name": "Security Affairs",
            "url": "https://securityaffairs.co/wordpress/feed",
            "source": "SecurityAffairs"
        }
    ]
    
    @track_time(PARSER_DURATION, source="rss_feeds")
    async def parse_articles(self, url: str = None) -> List[Dict[str, Any]]:
        """Parse articles from RSS feeds."""
        all_articles = []
        
        for feed_info in self.RSS_FEEDS:
            try:
                self.log_info(f"Trying RSS feed: {feed_info['name']}")
                
                # Fetch RSS feed
                articles = await self._parse_rss_feed(feed_info)
                if articles:
                    self.log_info(f"Found {len(articles)} articles from {feed_info['name']}")
                    all_articles.extend(articles)
                    
                    # If we got articles from first source, that's enough
                    if len(all_articles) >= 5:
                        break
                        
            except Exception as e:
                self.log_warning(f"Failed to parse RSS {feed_info['name']}", error=str(e))
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
            
            self.log_info("Parsed articles from RSS feeds", count=len(final_articles))
            return final_articles
        
        self.log_warning("No articles found from any RSS feed")
        return []
    
    async def _parse_rss_feed(self, feed_info: Dict) -> List[Dict[str, Any]]:
        """Parse a single RSS feed."""
        articles = []
        
        try:
            # Fetch RSS content
            html = await self.fetch_page(feed_info["url"])
            
            # Parse RSS
            feed = feedparser.parse(html)
            
            if not feed.entries:
                self.log_warning(f"No entries found in RSS feed {feed_info['name']}")
                return []
            
            # Process entries
            for entry in feed.entries[:10]:  # Limit to 10 most recent
                article_data = self._parse_rss_entry(entry, feed_info)
                if article_data:
                    articles.append(article_data)
                    
        except Exception as e:
            self.log_warning(f"Failed to parse RSS feed {feed_info['name']}", error=str(e))
        
        return articles
    
    def _parse_rss_entry(self, entry, feed_info: Dict) -> Optional[Dict[str, Any]]:
        """Parse a single RSS entry."""
        try:
            # Extract title
            title = getattr(entry, 'title', '').strip()
            if not title or len(title) < 10:
                return None
            
            # Extract URL
            url = getattr(entry, 'link', '').strip()
            if not url:
                return None
            
            # Extract description/summary
            description = None
            if hasattr(entry, 'summary'):
                description = entry.summary.strip()
                # Remove HTML tags from description
                description = re.sub(r'<[^>]+>', '', description)
                description = re.sub(r'\s+', ' ', description).strip()
                
                if len(description) > 300:
                    description = description[:297] + "..."
            
            # Extract published date
            published_at = datetime.utcnow()  # Default to now
            
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except (TypeError, ValueError):
                    pass
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                try:
                    published_at = datetime(*entry.updated_parsed[:6])
                except (TypeError, ValueError):
                    pass
            
            return {
                "title": title,
                "url": url,
                "description": description,
                "published_at": published_at,
                "source": feed_info["source"]
            }
            
        except Exception as e:
            self.log_warning("Failed to parse RSS entry", error=str(e))
            return None
    
    def extract_article_data(self, element) -> Optional[Dict[str, Any]]:
        """Compatibility method - not used for RSS parsing."""
        return None