"""
PostgreSQL connection management for WMS Catalog Scraper.

Provides async connection pooling and database initialization.
"""

import os
from typing import Optional
import asyncpg
from loguru import logger
from contextlib import asynccontextmanager


# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_connection_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "25060")),
            database=os.getenv("DB_NAME", "defaultdb"),
            user=os.getenv("DB_USER", "doadmin"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database connection pool created")
    
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a connection from the pool."""
    pool = await get_connection_pool()
    async with pool.acquire() as conn:
        yield conn


async def init_db():
    """Initialize database tables if they don't exist."""
    pool = await get_connection_pool()
    
    create_parts_table = """
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
    );
    """
    
    create_sync_log_table = """
    CREATE TABLE IF NOT EXISTS catalog_sync_log (
        id SERIAL PRIMARY KEY,
        supplier VARCHAR(50) NOT NULL,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        status VARCHAR(20),
        parts_scraped INTEGER DEFAULT 0,
        parts_updated INTEGER DEFAULT 0,
        error_message TEXT
    );
    """
    
    create_updated_at_trigger = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """
    
    create_trigger = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'update_catalog_parts_updated_at'
        ) THEN
            CREATE TRIGGER update_catalog_parts_updated_at
                BEFORE UPDATE ON catalog_parts
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        END IF;
    END;
    $$;
    """
    
    async with pool.acquire() as conn:
        await conn.execute(create_parts_table)
        await conn.execute(create_sync_log_table)
        await conn.execute(create_updated_at_trigger)
        await conn.execute(create_trigger)
        logger.info("Database tables initialized")


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
