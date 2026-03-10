"""
Scrapy pipelines for WMS Catalog Scraper.
"""

import asyncio
import asyncpg
from datetime import datetime
from typing import Optional
from loguru import logger
from scrapy.exceptions import DropItem

from .items import CatalogPartItem


class WmsScraperPipeline:
    """
    Pipeline to process and store catalog items in PostgreSQL.
    """
    
    def __init__(self, db_host, db_port, db_name, db_user, db_password):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.pool: Optional[asyncpg.Pool] = None
        self.items_processed = 0
        self.items_updated = 0
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            db_host=crawler.settings.get('DB_HOST'),
            db_port=crawler.settings.getint('DB_PORT'),
            db_name=crawler.settings.get('DB_NAME'),
            db_user=crawler.settings.get('DB_USER'),
            db_password=crawler.settings.get('DB_PASSWORD'),
        )
    
    async def open_spider(self, spider):
        """Create database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                min_size=2,
                max_size=10,
            )
            logger.info("Database connection pool created")
            
            # Ensure tables exist
            await self._init_tables()
            
            # Log sync start
            await self._log_sync_start(spider.name)
            
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def close_spider(self, spider):
        """Close database pool and log sync completion."""
        # Update sync log
        await self._log_sync_complete(spider.name, 'success')
        
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
        
        logger.info(f"Pipeline stats: {self.items_processed} processed, {self.items_updated} updated")
    
    async def _init_tables(self):
        """Create tables if they don't exist."""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS catalog_parts (
                    id SERIAL PRIMARY KEY,
                    sku VARCHAR(100) NOT NULL,
                    supplier VARCHAR(50) NOT NULL,
                    description TEXT,
                    category VARCHAR(100),
                    subcategory VARCHAR(100),
                    brand VARCHAR(100),
                    oem_number VARCHAR(100),
                    cost_price DECIMAL(10, 2),
                    retail_price DECIMAL(10, 2),
                    stock_quantity INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sku, supplier)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS catalog_sync_log (
                    id SERIAL PRIMARY KEY,
                    supplier VARCHAR(50) NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status VARCHAR(20),
                    parts_scraped INTEGER DEFAULT 0,
                    parts_updated INTEGER DEFAULT 0,
                    error_message TEXT
                )
            ''')
            
            logger.info("Database tables verified")
    
    async def _log_sync_start(self, supplier: str):
        """Log sync start."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO catalog_sync_log (supplier, started_at, status) VALUES ($1, $2, $3)",
                supplier, datetime.now(), 'running'
            )
    
    async def _log_sync_complete(self, supplier: str, status: str):
        """Log sync completion."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE catalog_sync_log 
                SET completed_at = $1, status = $2, parts_scraped = $3, parts_updated = $4
                WHERE supplier = $5 AND completed_at IS NULL
                """,
                datetime.now(), status, self.items_processed, self.items_updated, supplier
            )
    
    def process_item(self, item, spider):
        """Process and store item."""
        if isinstance(item, CatalogPartItem):
            # Run async database operation
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._upsert_item(item))
        return item
    
    async def _upsert_item(self, item: CatalogPartItem):
        """Insert or update item in database."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    INSERT INTO catalog_parts 
                    (sku, supplier, description, category, subcategory, brand, oem_number,
                     cost_price, retail_price, stock_quantity)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (sku, supplier) DO UPDATE SET
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        subcategory = EXCLUDED.subcategory,
                        brand = EXCLUDED.brand,
                        oem_number = EXCLUDED.oem_number,
                        cost_price = EXCLUDED.cost_price,
                        retail_price = EXCLUDED.retail_price,
                        stock_quantity = EXCLUDED.stock_quantity,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    item.get('sku'),
                    item.get('supplier'),
                    item.get('description'),
                    item.get('category'),
                    item.get('subcategory'),
                    item.get('brand'),
                    item.get('oem_number'),
                    item.get('cost_price'),
                    item.get('retail_price'),
                    item.get('stock_quantity', 0),
                )
                
                self.items_processed += 1
                if 'UPDATE' in result:
                    self.items_updated += 1
                
                if self.items_processed % 100 == 0:
                    logger.info(f"Processed {self.items_processed} items...")
                    
        except Exception as e:
            logger.error(f"Error upserting item {item.get('sku')}: {e}")


class DuplicatesPipeline:
    """
    Pipeline to filter duplicate items.
    """
    
    def __init__(self):
        self.seen = set()
    
    def process_item(self, item, spider):
        if isinstance(item, CatalogPartItem):
            key = f"{item.get('supplier')}:{item.get('sku')}"
            if key in self.seen:
                raise DropItem(f"Duplicate item: {key}")
            self.seen.add(key)
        return item


class ValidationPipeline:
    """
    Pipeline to validate items.
    """
    
    def process_item(self, item, spider):
        if isinstance(item, CatalogPartItem):
            # Ensure required fields
            if not item.get('sku'):
                raise DropItem("Missing SKU")
            if not item.get('supplier'):
                raise DropItem("Missing supplier")
        return item
