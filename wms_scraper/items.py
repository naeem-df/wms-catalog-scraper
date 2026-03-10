"""
Scrapy items for WMS Catalog Scraper.
"""

import scrapy
from typing import Optional
from decimal import Decimal


class CatalogPartItem(scrapy.Item):
    """Item representing a part from the catalog."""
    
    # Required fields
    sku = scrapy.Field()
    supplier = scrapy.Field()
    
    # Optional fields
    description = scrapy.Field()
    category = scrapy.Field()
    subcategory = scrapy.Field()
    brand = scrapy.Field()
    oem_number = scrapy.Field()
    cost_price = scrapy.Field()
    retail_price = scrapy.Field()
    stock_quantity = scrapy.Field()
    
    # Metadata
    source_url = scrapy.Field()
    scraped_at = scrapy.Field()


class SyncLogItem(scrapy.Item):
    """Item for sync logging."""
    
    supplier = scrapy.Field()
    started_at = scrapy.Field()
    completed_at = scrapy.Field()
    status = scrapy.Field()
    parts_scraped = scrapy.Field()
    parts_updated = scrapy.Field()
    error_message = scrapy.Field()
