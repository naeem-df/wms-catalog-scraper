"""
Image Pipeline for WMS Catalog Scraper

Downloads product images and stores them locally or in cloud storage.
Saves image paths to database instead of URLs.
"""
import os
import hashlib
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from itemadapter import ItemAdapter
from loguru import logger


class ImageDownloadPipeline:
    """
    Downloads product images during scraping.
    
    Features:
    - Async image downloads
    - Hash-based filename generation
    - Local storage with optional S3 upload
    - Retry logic for failed downloads
    """
    
    def __init__(self):
        self.images_dir = Path(os.environ.get('IMAGES_DIR', '/var/www/wms-images'))
        self.images_url_prefix = os.environ.get('IMAGES_URL_PREFIX', 'https://images.wmsgroup.co.za')
        self.max_retries = 3
        self.timeout = 30
        
        # Create images directory
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Session for async downloads
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
        return self.session
    
    def _generate_filename(self, url: str, sku: str, supplier: str) -> str:
        """Generate unique filename from URL and SKU."""
        # Extract extension from URL
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        
        # Create hash from URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Clean SKU for filename
        clean_sku = re.sub(r'[^\w\-]', '_', sku) if sku else 'unknown'
        
        # Format: {supplier}_{sku}_{hash}.ext
        filename = f"{supplier}_{clean_sku}_{url_hash}{ext}"
        return filename.lower()
    
    async def _download_image(self, url: str, filepath: Path) -> bool:
        """Download image from URL to filepath."""
        session = await self._get_session()
        
        for attempt in range(self.max_retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        filepath.write_bytes(content)
                        logger.debug(f"Downloaded: {url} -> {filepath}")
                        return True
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {url} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
        
        return False
    
    async def process_item(self, item: dict, spider) -> dict:
        """Process item and download images."""
        adapter = ItemAdapter(item)
        
        # Get image URLs from item
        image_urls = adapter.get('image_urls', [])
        sku = adapter.get('sku', '')
        supplier = adapter.get('supplier', 'unknown')
        
        if not image_urls:
            adapter['image_paths'] = []
            return item
        
        # Download each image
        image_paths = []
        
        for url in image_urls:
            if not url:
                continue
            
            # Generate filename
            filename = self._generate_filename(url, sku, supplier)
            filepath = self.images_dir / filename
            
            # Download if not exists
            if not filepath.exists():
                success = await self._download_image(url, filepath)
                if not success:
                    continue
            
            # Store relative path for database
            relative_path = f"/images/{filename}"
            image_paths.append(relative_path)
        
        adapter['image_paths'] = image_paths
        adapter['image_url'] = image_paths[0] if image_paths else None
        
        return item
    
    def close_spider(self, spider):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            asyncio.get_event_loop().run_until_complete(self.session.close())


# For synchronous Scrapy (alternative)
import re
import requests
from scrapy.pipelines.images import ImagesPipeline as ScrapyImagesPipeline


class LocalImagePipeline:
    """
    Synchronous image download pipeline (fallback).
    
    Uses requests library for simpler setup.
    """
    
    def __init__(self):
        self.images_dir = Path(os.environ.get('IMAGES_DIR', '/var/www/wms-images'))
        self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_filename(self, url: str, sku: str, supplier: str) -> str:
        """Generate unique filename."""
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        clean_sku = re.sub(r'[^\w\-]', '_', sku) if sku else 'unknown'
        return f"{supplier}_{clean_sku}_{url_hash}{ext}".lower()
    
    def process_item(self, item: dict, spider) -> dict:
        """Download images synchronously."""
        image_urls = item.get('image_urls', [])
        sku = item.get('sku', '')
        supplier = item.get('supplier', 'unknown')
        
        image_paths = []
        
        for url in image_urls:
            if not url:
                continue
            
            filename = self._generate_filename(url, sku, supplier)
            filepath = self.images_dir / filename
            
            # Download if not exists
            if not filepath.exists():
                try:
                    response = requests.get(url, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if response.status_code == 200:
                        filepath.write_bytes(response.content)
                        logger.debug(f"Downloaded: {url}")
                except Exception as e:
                    logger.error(f"Failed to download {url}: {e}")
                    continue
            
            image_paths.append(f"/images/{filename}")
        
        item['image_paths'] = image_paths
        item['image_url'] = image_paths[0] if image_paths else None
        
        return item