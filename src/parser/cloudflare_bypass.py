import asyncio
import aiohttp
from typing import Optional, Dict, Any
from src.utils import LoggerMixin


class CloudflareBypass(LoggerMixin):
    """Handles Cloudflare anti-bot protection bypass."""
    
    def __init__(self):
        self.cookies: Dict[str, str] = {}
        
    async def get_with_bypass(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Fetch page with Cloudflare bypass attempts."""
        
        # First, try normal request
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    text = await response.text()
                    
                    # Check if we hit Cloudflare challenge
                    if self._is_cloudflare_challenge(text):
                        self.log_warning("Cloudflare challenge detected", url=url)
                        # Try alternative methods
                        return await self._bypass_cloudflare(session, url, headers)
                    
                    return text
                    
        except Exception as e:
            self.log_error(f"Failed to fetch with bypass: {e}")
            raise
    
    def _is_cloudflare_challenge(self, html: str) -> bool:
        """Check if the response is a Cloudflare challenge page."""
        cloudflare_indicators = [
            "Checking your browser",
            "cf-browser-verification",
            "cf_clearance",
            "__cf_chl_jschl_tk__",
            "Cloudflare Ray ID",
            "challenges.cloudflare.com"
        ]
        
        return any(indicator in html for indicator in cloudflare_indicators)
    
    async def _bypass_cloudflare(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Attempt to bypass Cloudflare protection."""
        
        # Method 1: Use different headers
        bypass_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        if headers:
            bypass_headers.update(headers)
        
        # Add delay to appear more human-like
        await asyncio.sleep(2)
        
        try:
            async with session.get(url, headers=bypass_headers) as response:
                return await response.text()
        except Exception as e:
            self.log_error(f"Cloudflare bypass failed: {e}")
            
            # Method 2: Try with cookies from a previous successful session
            if self.cookies:
                try:
                    cookie_header = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
                    bypass_headers["Cookie"] = cookie_header
                    
                    async with session.get(url, headers=bypass_headers) as response:
                        return await response.text()
                except Exception:
                    pass
            
            # If all methods fail, raise the original error
            raise Exception(f"Unable to bypass Cloudflare protection for {url}")
    
    def save_cookies(self, cookies: Dict[str, str]):
        """Save cookies from a successful session."""
        self.cookies.update(cookies)


# Global instance
cloudflare_bypass = CloudflareBypass()