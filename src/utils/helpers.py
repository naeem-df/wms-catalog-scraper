"""
Utility functions for WMS Catalog Scraper.
"""

import os
import asyncio
import functools
from typing import Optional, Callable, Any
from decimal import Decimal

import aiohttp
from loguru import logger


async def send_telegram_message(
    message: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None
) -> bool:
    """
    Send a message via Telegram.
    
    Args:
        message: Message text to send
        bot_token: Telegram bot token (from env if not provided)
        chat_id: Telegram chat ID (from env if not provided)
    
    Returns:
        True if message sent successfully
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.warning("Telegram credentials not configured, skipping notification")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            ) as response:
                if response.status == 200:
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Failed to send Telegram message: {error}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def setup_logging(log_file: str = "logs/scraper.log"):
    """
    Configure loguru logging.
    
    Args:
        log_file: Path to log file
    """
    import sys
    from pathlib import Path
    
    # Create logs directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Add file handler
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )
    
    logger.info("Logging configured")


def calculate_gp(cost: float, retail: float) -> float:
    """
    Calculate gross profit percentage.
    
    Args:
        cost: Cost price
        retail: Retail price (including VAT)
    
    Returns:
        GP percentage
    """
    if not retail or retail <= 0:
        return 0.0
    
    # Remove VAT (15%)
    retail_ex_vat = retail / 1.15
    
    # Calculate GP
    gp = ((retail_ex_vat - cost) / retail_ex_vat) * 100
    
    return round(gp, 2)


def format_currency(amount: float, currency: str = "R") -> str:
    """
    Format a number as currency.
    
    Args:
        amount: Amount to format
        currency: Currency symbol (default: R for Rand)
    
    Returns:
        Formatted currency string
    """
    return f"{currency}{amount:,.2f}"


def retry_on_failure(max_retries: int = 3, delay: float = 5.0, backoff: float = 2.0):
    """
    Decorator to retry a function on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
    """
    import asyncio
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        raise last_error
            
            raise last_error
        
        return wrapper
    
    return decorator
