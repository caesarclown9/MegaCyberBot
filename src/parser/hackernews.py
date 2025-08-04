from typing import List, Dict, Any, Optional
from datetime import datetime
import re
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from src.utils import track_time, PARSER_DURATION
from src.config import settings
from .base import BaseParser


class HackerNewsParser(BaseParser):
    """Parser for The Hacker News cybersecurity website."""
    
    BASE_URL = "https://thehackernews.com/"
    NEWS_URL = "https://thehackernews.com/"
    
    @track_time(PARSER_DURATION, source="hackernews_html")
    async def parse_articles(self, url: str = None) -> List[Dict[str, Any]]:
        """Parse articles from The Hacker News."""
        url = url or self.NEWS_URL
        articles = []
        
        try:
            html = await self.fetch_page(url)
            soup = self.parse_html(html)
            
            # Find article containers - The Hacker News uses different classes
            article_containers = (
                soup.find_all("div", class_="body-post") or
                soup.find_all("article") or 
                soup.find_all("div", class_="story-link") or
                soup.find_all("div", class_="clear home-right")
            )
            
            if not article_containers:
                # Try finding links that look like article URLs
                article_links = soup.find_all("a", href=re.compile(r'/\d{4}/\d{2}/'))
                for i, link in enumerate(article_links[:15]):  # Limit to 15 most recent
                    article_url = urljoin(self.BASE_URL, link.get('href'))
                    self.log_info(f"Parsing article {i+1}/15: {article_url}")
                    
                    # Add delay between requests to avoid being blocked
                    if i > 0:
                        await asyncio.sleep(1)
                    
                    article_data = await self._parse_article_page(article_url)
                    if article_data:
                        # Check date filter
                        article_date = article_data.get("published_at")
                        if article_date and article_date < settings.min_article_datetime:
                            self.log_info(f"Skipping old article: {article_date} < {settings.min_article_datetime}")
                            continue
                        articles.append(article_data)
                        self.log_info(f"Successfully parsed article: {article_data.get('title', 'Unknown')[:50]}...")
            else:
                self.log_info(f"Found {len(article_containers)} article containers")
                
                for i, container in enumerate(article_containers[:15], 1):  # Limit to 15 most recent
                    article_data = self.extract_article_data(container)
                    if article_data:
                        # Add delay between requests to avoid being blocked
                        if i > 1:
                            await asyncio.sleep(1)
                        
                        # Parse full article page for better content
                        full_article = await self._parse_article_page(article_data["url"])
                        if full_article:
                            article_data.update(full_article)
                        
                        # Check date filter
                        article_date = article_data.get("published_at")
                        if article_date and article_date < settings.min_article_datetime:
                            self.log_info(f"Skipping old article: {article_date} < {settings.min_article_datetime}")
                            continue
                        articles.append(article_data)
                        self.log_info(f"Successfully parsed article {i}: {article_data.get('title', 'Unknown')[:50]}...")
            
            self.log_info("Parsed articles from The Hacker News", count=len(articles))
            
        except Exception as e:
            self.log_error("Failed to parse articles from The Hacker News", error=str(e))
            raise e
        
        return articles
    
    async def _parse_article_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Parse individual article page from The Hacker News."""
        try:
            html = await self.fetch_page(url)
            soup = self.parse_html(html)
            
            # Find article container
            article_elem = (
                soup.find("div", class_="articlebody") or
                soup.find("div", class_="story-body") or
                soup.find("article") or
                soup.find("div", class_="post-body") or
                soup.find("div", class_="entry-content")
            )
            
            if not article_elem:
                self.log_warning(f"No article container found for {url}")
                article_elem = soup
            
            # Extract title
            title_elem = (
                soup.find("h1", class_="story-title") or
                soup.find("h1", class_="entry-title") or
                soup.find("h1") or
                soup.find("title")
            )
            
            if not title_elem:
                self.log_warning(f"No title found for {url}")
                return None
            
            title = self.clean_text(title_elem.get_text())
            
            # Extract content for description
            content_paragraphs = article_elem.find_all("p")
            description = None
            
            if content_paragraphs:
                # Get first meaningful paragraph
                for p in content_paragraphs:
                    text = self.clean_text(p.get_text())
                    if text and len(text) > 30:  # Skip very short paragraphs
                        description = text
                        break
                
                if description and len(description) > 300:
                    description = description[:297] + "..."
            
            # If no description from paragraphs, use limited content
            if not description:
                content_text = article_elem.get_text()
                description = self.clean_text(content_text[:300]) + "..."
            
            # Extract date - The Hacker News typically has date in meta tags or time elements
            published_at = None
            
            # Try to find date in meta tags
            date_meta = (
                soup.find("meta", property="article:published_time") or
                soup.find("meta", name="publishdate") or
                soup.find("meta", property="og:published_time")
            )
            
            if date_meta and date_meta.get("content"):
                published_at = self.parse_date(date_meta["content"])
            
            # Try to find date in time elements
            if not published_at:
                time_elem = soup.find("time")
                if time_elem:
                    datetime_attr = time_elem.get("datetime") or time_elem.get_text()
                    if datetime_attr:
                        published_at = self.parse_date(datetime_attr)
            
            # Try to find date in URL pattern (common format: /YYYY/MM/)
            if not published_at:
                date_match = re.search(r'/(\d{4})/(\d{2})/', url)
                if date_match:
                    year, month = date_match.groups()
                    try:
                        published_at = datetime(int(year), int(month), 1)
                    except ValueError:
                        pass
            
            # Try to find date in article text
            if not published_at:
                article_text = soup.get_text()
                # Look for common date formats
                date_patterns = [
                    r'(\w+\s+\d{1,2},\s+\d{4})',  # August 4, 2025
                    r'(\d{1,2}\s+\w+\s+\d{4})',   # 4 August 2025
                    r'(\d{4}-\d{2}-\d{2})',       # 2025-08-04
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, article_text)
                    if match:
                        published_at = self.parse_date(match.group(1))
                        if published_at:
                            break
            
            self.log_info(f"Parsed article: title='{title[:50]}...', date={published_at}")
            
            return {
                "title": title,
                "url": url,
                "description": description,
                "published_at": published_at or datetime.utcnow(),
            }
            
        except Exception as e:
            self.log_warning(f"Failed to parse article page {url}", error=str(e))
            return None
    
    def extract_article_data(self, element: Tag) -> Optional[Dict[str, Any]]:
        """Extract data from an article element."""
        try:
            # Find the article link
            link_elem = (
                element.find("a", href=re.compile(r'/\d{4}/\d{2}/')) or
                element.find("a")
            )
            
            if not link_elem or not link_elem.get("href"):
                return None
            
            url = urljoin(self.BASE_URL, link_elem["href"])
            
            # Extract title
            title = None
            title_elem = (
                element.find("h2") or
                element.find("h3") or
                link_elem
            )
            
            if title_elem:
                title = self.clean_text(title_elem.get_text())
            
            if not title:
                return None
            
            # Try to extract description from the element
            description = None
            desc_elem = element.find("p")
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())
                if description and len(description) > 300:
                    description = description[:297] + "..."
            
            return {
                "title": title,
                "url": url,
                "description": description,
                "published_at": datetime.utcnow(),  # Will be updated when parsing full article
            }
            
        except Exception as e:
            self.log_warning("Failed to extract article data", error=str(e))
            return None