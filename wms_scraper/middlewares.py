"""
Scrapy middlewares for WMS Catalog Scraper.
"""

import random
from scrapy import signals
from scrapy.http import Request, Response
from loguru import logger


class WmsScraperSpiderMiddleware:
    """
    Spider middleware for WMS Catalog Scraper.
    """
    
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s
    
    def process_spider_input(self, response, spider):
        return None
    
    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i
    
    def process_spider_exception(self, response, exception, spider):
        logger.error(f"Spider exception in {spider.name}: {exception}")
    
    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r
    
    def spider_opened(self, spider):
        logger.info(f"Spider opened: {spider.name}")


class WmsScraperDownloaderMiddleware:
    """
    Downloader middleware for WMS Catalog Scraper.
    """
    
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s
    
    def process_request(self, request, spider):
        # Add random delay to requests
        if hasattr(spider, 'random_delay'):
            request.meta['download_delay'] = random.uniform(
                spider.settings.getfloat('DOWNLOAD_DELAY', 2),
                spider.settings.getfloat('DOWNLOAD_DELAY', 2) * 2
            )
        return None
    
    def process_response(self, request, response, spider):
        return response
    
    def process_exception(self, request, exception, spider):
        logger.error(f"Request failed: {request.url} - {exception}")
        return None
    
    def spider_opened(self, spider):
        logger.info(f"Spider opened: {spider.name}")


class AntiBotMiddleware:
    """
    Middleware to help evade bot detection.
    """
    
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]
    
    def process_request(self, request, spider):
        # Rotate user agents
        if 'playwright' in request.meta:
            request.meta['playwright_context_kwargs'] = {
                'user_agent': random.choice(self.user_agents)
            }
        return None
