"""
Pydantic data models for WMS Catalog Scraper.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator
from decimal import Decimal


class Part(BaseModel):
    """Represents a part from a catalog."""
    
    sku: str = Field(..., min_length=1, max_length=100, description="Part SKU/Number")
    supplier: str = Field(..., min_length=1, max_length=50, description="Supplier name (alert/motus)")
    description: Optional[str] = Field(None, description="Part description")
    category: Optional[str] = Field(None, max_length=100, description="Main category")
    subcategory: Optional[str] = Field(None, max_length=100, description="Subcategory")
    brand: Optional[str] = Field(None, max_length=100, description="Brand name")
    oem_number: Optional[str] = Field(None, max_length=100, description="OEM part number")
    cost_price: Optional[Decimal] = Field(None, ge=0, description="Cost price")
    retail_price: Optional[Decimal] = Field(None, ge=0, description="Retail price")
    stock_quantity: int = Field(default=0, ge=0, description="Stock quantity")
    
    @validator('supplier')
    def validate_supplier(cls, v):
        """Ensure supplier is lowercase."""
        return v.lower()
    
    @validator('sku')
    def validate_sku(cls, v):
        """Trim whitespace from SKU."""
        return v.strip()
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v else None
        }


class SyncLog(BaseModel):
    """Represents a sync log entry."""
    
    supplier: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, success, failed
    parts_scraped: int = 0
    parts_updated: int = 0
    error_message: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        """Ensure status is valid."""
        allowed = ['running', 'success', 'failed']
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v


class ScraperConfig(BaseModel):
    """Configuration for the scraper."""
    
    headless: bool = True
    delay_min: float = 2.0
    delay_max: float = 5.0
    max_retries: int = 3
    
    # URLs
    alert_url: str = "https://web1.carparts-cat.com/default.aspx?10=7FD0A9CE5E4D41DEACA81956B6408394494004&14=4&12=1003"
    motus_url: str = "https://web1.carparts-cat.com"
    
    # Database
    db_host: str = "localhost"
    db_port: int = 25060
    db_name: str = "defaultdb"
    db_user: str = "doadmin"
    db_password: str = ""
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
