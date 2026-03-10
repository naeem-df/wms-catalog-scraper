"""
Scrapy settings for WMS Catalog Scraper project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Scrapy settings

BOT_NAME = "wms_scraper"
SPIDER_MODULES = ["wms_scraper.spiders"]
NEWSPIDER_MODULE = "wms_scraper.spiders"

# Crawl responsibly by identifying yourself
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Configure a delay for requests
DOWNLOAD_DELAY = float(os.getenv("SCRAPER_DELAY_MIN", "2"))

# Randomize download delay
RANDOMIZE_DOWNLOAD_DELAY = True

# Timeout settings
DOWNLOAD_TIMEOUT = 60

# Enable Playwright for JavaScript rendering
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Playwright settings
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": os.getenv("SCRAPER_HEADLESS", "true").lower() == "true",
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
    ],
}

# Playwright page initialization scripts for anti-bot evasion
PLAYWRIGHT_PROCESS_REQUEST_HEADERS = lambda headers, request: {
    **headers,
    "Accept-Language": "en-ZA,en;q=0.9",
}

# Context settings for each page
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": USER_AGENT,
        "locale": "en-ZA",
        "timezone_id": "Africa/Johannesburg",
    }
}

# Configure item pipelines
ITEM_PIPELINES = {
    "wms_scraper.pipelines.LocalImagePipeline": 100,  # Download images first
    "wms_scraper.pipelines.WmsScraperPipeline": 300,  # Then save to database
}

# Image settings
IMAGES_DIR = os.getenv("IMAGES_DIR", "/var/www/wms-images")
IMAGES_URL_PREFIX = os.getenv("IMAGES_URL_PREFIX", "https://images.wmsgroup.co.za")

# Enable and configure HTTP caching
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Enable telnet console for debugging
TELNETCONSOLE_ENABLED = False

# Request fingerprinter
REQUEST_FINGERPRINTER_CLASS = "scrapy_playwright.request_fingerprinter.ScrapyPlaywrightRequestFingerprinter"

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Log settings
LOG_LEVEL = "INFO"
LOG_FILE = str(BASE_DIR / "logs" / "scrapy.log")

# Stats collection
STATS_CLASS = "scrapy.statscollectors.MemoryStatsCollector"

# Database settings (from environment)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "25060"))
DB_NAME = os.getenv("DB_NAME", "defaultdb")
DB_USER = os.getenv("DB_USER", "doadmin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Catalog credentials (from environment)
ALERT_USERNAME = os.getenv("ALERT_USERNAME", "")
ALERT_PASSWORD = os.getenv("ALERT_PASSWORD", "")
MOTUS_USERNAME = os.getenv("MOTUS_USERNAME", "")
MOTUS_PASSWORD = os.getenv("MOTUS_PASSWORD", "")

# Telegram notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
