import asyncio
import aiohttp
import random
from typing import Optional, List
from src.utils import LoggerMixin


class ProxyManager(LoggerMixin):
    """Manages proxy rotation for web requests."""
    
    # Free proxy services that might work (use at your own risk)
    FREE_PROXIES = [
        # These are examples, they may not work. Consider using a paid proxy service
        # "http://proxy1.example.com:8080",
        # "http://proxy2.example.com:3128",
    ]
    
    # Public proxy APIs (these fetch fresh proxy lists)
    PROXY_APIS = [
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all",
    ]
    
    def __init__(self):
        self.working_proxies: List[str] = []
        self.failed_proxies: set = set()
        self._last_fetch = None
        
    async def get_proxy(self) -> Optional[str]:
        """Get a working proxy from the pool."""
        # First try configured proxy
        from src.config import settings
        if settings.proxy_url:
            return settings.proxy_url
            
        # If no working proxies, try to fetch some
        if not self.working_proxies:
            await self.fetch_proxies()
            
        if not self.working_proxies:
            self.log_warning("No working proxies available")
            return None
            
        # Return random proxy from working list
        proxy = random.choice(self.working_proxies)
        return proxy
    
    async def fetch_proxies(self):
        """Fetch fresh proxy list from public APIs."""
        self.log_info("Fetching fresh proxy list")
        
        for api_url in self.PROXY_APIS:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, timeout=10) as response:
                        if response.status == 200:
                            text = await response.text()
                            # Parse proxy list (usually one per line)
                            proxies = text.strip().split('\n')
                            
                            # Validate and add proxies
                            for proxy in proxies[:10]:  # Limit to 10 for testing
                                proxy = proxy.strip()
                                if proxy and ':' in proxy:
                                    if not proxy.startswith('http'):
                                        proxy = f"http://{proxy}"
                                    
                                    # Test proxy
                                    if await self.test_proxy(proxy):
                                        self.working_proxies.append(proxy)
                                        self.log_info(f"Added working proxy: {proxy}")
                            
                            if self.working_proxies:
                                break
                                
            except Exception as e:
                self.log_warning(f"Failed to fetch proxies from {api_url}: {e}")
                continue
        
        self.log_info(f"Found {len(self.working_proxies)} working proxies")
    
    async def test_proxy(self, proxy: str, test_url: str = "http://httpbin.org/ip") -> bool:
        """Test if a proxy is working."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    test_url,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False
                ) as response:
                    if response.status == 200:
                        return True
        except Exception:
            pass
        
        return False
    
    def mark_proxy_failed(self, proxy: str):
        """Mark a proxy as failed and remove from working list."""
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            self.failed_proxies.add(proxy)
            self.log_warning(f"Proxy marked as failed: {proxy}")


# Global proxy manager instance
proxy_manager = ProxyManager()