"""
Alert catalog parser.

Handles navigation and data extraction from Alert auto parts catalog.
"""

import os
import random
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from playwright.async_api import Page
from loguru import logger

from ..auth import AuthSession
from ..database.models import Part


class AlertParser:
    """Parser for Alert auto parts catalog."""
    
    def __init__(self, headless: bool = True):
        """Initialize Alert parser."""
        self.supplier = "alert"
        self.headless = headless
        self.session: Optional[AuthSession] = None
        self.page: Optional[Page] = None
        self.parts_scraped = 0
        self.errors = []
    
    async def start(self):
        """Start browser and authenticate."""
        self.session = AuthSession("alert", headless=self.headless)
        self.page = await self.session.start()
        
        # Login
        success = await self.session.login()
        if not success:
            raise RuntimeError("Failed to login to Alert catalog")
        
        logger.info("Alert parser started and authenticated")
    
    async def scrape(self) -> List[Part]:
        """
        Main scraping method. Navigates catalog and extracts all parts.
        
        Returns:
            List of Part objects
        """
        if not self.page:
            await self.start()
        
        all_parts = []
        
        try:
            # Get all categories
            categories = await self._get_categories()
            logger.info(f"Found {len(categories)} categories in Alert catalog")
            
            for category in categories:
                try:
                    parts = await self._scrape_category(category)
                    all_parts.extend(parts)
                    self.parts_scraped += len(parts)
                    logger.info(f"Scraped {len(parts)} parts from category: {category['name']}")
                    
                    # Rate limiting
                    await self._random_delay()
                    
                except Exception as e:
                    logger.error(f"Error scraping category {category['name']}: {e}")
                    self.errors.append(f"Category {category['name']}: {str(e)}")
                    continue
            
            logger.info(f"Total parts scraped from Alert: {len(all_parts)}")
            return all_parts
            
        except Exception as e:
            logger.error(f"Alert scraping failed: {e}")
            raise
    
    async def _get_categories(self) -> List[Dict[str, str]]:
        """Get list of all categories from the catalog."""
        categories = []
        
        try:
            # Wait for page to load
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            
            # Common category selectors for TopMotive
            category_selectors = [
                '.category-list a',
                '.nav-categories a',
                '#categories a',
                'a[href*="category"]',
                '.menu-item a',
            ]
            
            for selector in category_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        for elem in elements:
                            href = await elem.get_attribute('href')
                            text = await elem.inner_text()
                            if text.strip() and href:
                                categories.append({
                                    'name': text.strip(),
                                    'url': href if href.startswith('http') else f"https://web1.carparts-cat.com{href}"
                                })
                        if categories:
                            break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # If no categories found via selectors, try to extract from page content
            if not categories:
                logger.info("Attempting to extract categories from page content")
                categories = await self._extract_categories_from_page()
            
            return categories
            
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    async def _extract_categories_from_page(self) -> List[Dict[str, str]]:
        """Extract categories from page content when selectors fail."""
        categories = []
        
        try:
            # Get all links on the page
            links = await self.page.query_selector_all('a')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    
                    # Filter for category-like links
                    if href and text and len(text.strip()) > 0:
                        # Skip navigation links
                        skip_patterns = ['login', 'logout', 'register', 'contact', 'about', 'help']
                        if any(p in href.lower() for p in skip_patterns):
                            continue
                        
                        # Look for category indicators
                        if any(p in href.lower() for p in ['cat', 'category', 'group', 'section']):
                            categories.append({
                                'name': text.strip(),
                                'url': href if href.startswith('http') else f"https://web1.carparts-cat.com{href}"
                            })
                except:
                    continue
            
            logger.info(f"Extracted {len(categories)} potential categories from page")
            return categories
            
        except Exception as e:
            logger.error(f"Error extracting categories from page: {e}")
            return []
    
    async def _scrape_category(self, category: Dict[str, str]) -> List[Part]:
        """Scrape all parts from a category."""
        parts = []
        
        try:
            # Navigate to category
            await self.page.goto(category['url'], wait_until='networkidle', timeout=60000)
            await self._random_delay()
            
            # Check for subcategories
            subcategories = await self._get_subcategories()
            
            if subcategories:
                # Recursively scrape subcategories
                for subcat in subcategories:
                    subcat_parts = await self._scrape_category(subcat)
                    parts.extend(subcat_parts)
            else:
                # Scrape products on this page
                page_parts = await self._scrape_products(category['name'])
                parts.extend(page_parts)
                
                # Check for pagination
                has_next = await self._has_next_page()
                while has_next:
                    await self._next_page()
                    await self._random_delay()
                    page_parts = await self._scrape_products(category['name'])
                    parts.extend(page_parts)
                    has_next = await self._has_next_page()
            
            return parts
            
        except Exception as e:
            logger.error(f"Error scraping category {category['name']}: {e}")
            return parts
    
    async def _get_subcategories(self) -> List[Dict[str, str]]:
        """Check if current page has subcategories."""
        subcategories = []
        
        subcategory_selectors = [
            '.subcategory-list a',
            '.subcategories a',
            'a[href*="subcategory"]',
        ]
        
        for selector in subcategory_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    for elem in elements:
                        href = await elem.get_attribute('href')
                        text = await elem.inner_text()
                        if text.strip() and href:
                            subcategories.append({
                                'name': text.strip(),
                                'url': href if href.startswith('http') else f"https://web1.carparts-cat.com{href}"
                            })
                    if subcategories:
                        break
            except:
                continue
        
        return subcategories
    
    async def _scrape_products(self, category_name: str) -> List[Part]:
        """Scrape product listings from current page."""
        parts = []
        
        try:
            # Common product list selectors
            product_selectors = [
                '.product-item',
                '.product-listing tr',
                '.parts-table tr',
                'tr[class*="product"]',
                'tr[class*="part"]',
            ]
            
            product_rows = []
            for selector in product_selectors:
                try:
                    rows = await self.page.query_selector_all(selector)
                    if rows:
                        product_rows = rows
                        break
                except:
                    continue
            
            for row in product_rows:
                try:
                    part = await self._extract_part_from_row(row, category_name)
                    if part:
                        parts.append(part)
                except Exception as e:
                    logger.debug(f"Error extracting part from row: {e}")
                    continue
            
            return parts
            
        except Exception as e:
            logger.error(f"Error scraping products: {e}")
            return parts
    
    async def _extract_part_from_row(self, row, category_name: str) -> Optional[Part]:
        """Extract part data from a product row."""
        try:
            # Get all cells/columns
            cells = await row.query_selector_all('td')
            if not cells:
                # Try as div-based layout
                cells = await row.query_selector_all('div')
            
            if not cells:
                return None
            
            # Extract text from each cell
            cell_texts = []
            for cell in cells:
                text = await cell.inner_text()
                cell_texts.append(text.strip())
            
            # Try to identify fields by content patterns
            sku = None
            description = None
            brand = None
            oem_number = None
            cost_price = None
            retail_price = None
            stock_quantity = 0
            
            for i, text in enumerate(cell_texts):
                text = text.strip()
                if not text:
                    continue
                
                # SKU detection (alphanumeric codes)
                if not sku and re.match(r'^[A-Z0-9\-\/]+$', text, re.IGNORECASE):
                    sku = text
                
                # Price detection (contains currency symbols or decimals)
                elif not retail_price and re.search(r'[R$€£]|[\d]+\.[\d]{2}', text):
                    # Clean price string
                    price_str = re.sub(r'[^\d.]', '', text)
                    try:
                        retail_price = float(price_str) if price_str else None
                    except:
                        pass
                
                # Brand detection (known brand patterns)
                elif not brand and any(b in text.upper() for b in ['BOSCH', 'VALEO', 'HELLA', 'NGK', 'BREMBO', 'FAG', 'SKF', 'GATES', 'DAYCO', 'CONTINENTAL']):
                    brand = text.title()
                
                # OEM number detection (contains numbers and possibly letters)
                elif not oem_number and re.match(r'^[A-Z0-9\s\-\/]+$', text, re.IGNORECASE) and len(text) > 5:
                    oem_number = text
                
                # Description (longer text)
                elif not description and len(text) > 10:
                    description = text
            
            # If we have at least a SKU, create the part
            if sku or description:
                return Part(
                    sku=sku or f"UNKNOWN-{hash(description or '')}",
                    supplier=self.supplier,
                    description=description,
                    category=category_name,
                    brand=brand,
                    oem_number=oem_number,
                    cost_price=cost_price,
                    retail_price=retail_price,
                    stock_quantity=stock_quantity
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting part: {e}")
            return None
    
    async def _has_next_page(self) -> bool:
        """Check if there's a next page of products."""
        next_selectors = [
            'a.next',
            'a[rel="next"]',
            'a:has-text("Next")',
            'a:has-text(">")',
            '.pagination a:last-child',
        ]
        
        for selector in next_selectors:
            try:
                elem = await self.page.query_selector(selector)
                if elem:
                    # Check if it's disabled
                    is_disabled = await elem.get_attribute('disabled')
                    if not is_disabled:
                        return True
            except:
                continue
        
        return False
    
    async def _next_page(self):
        """Navigate to next page of products."""
        next_selectors = [
            'a.next',
            'a[rel="next"]',
            'a:has-text("Next")',
            '.pagination a:last-child',
        ]
        
        for selector in next_selectors:
            try:
                elem = await self.page.query_selector(selector)
                if elem:
                    await elem.click()
                    await self.page.wait_for_load_state('networkidle', timeout=30000)
                    return
            except:
                continue
        
        logger.warning("Could not find next page button")
    
    async def _random_delay(self, min_seconds: float = None, max_seconds: float = None):
        """Add random delay for rate limiting."""
        min_s = min_seconds or float(os.getenv("SCRAPER_DELAY_MIN", "2"))
        max_s = max_seconds or float(os.getenv("SCRAPER_DELAY_MAX", "5"))
        
        delay = random.uniform(min_s, max_s)
        await self.page.wait_for_timeout(int(delay * 1000))
    
    async def close(self):
        """Close browser session."""
        if self.session:
            await self.session.close()
            logger.info("Alert parser closed")
