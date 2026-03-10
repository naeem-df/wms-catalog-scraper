"""
Motus catalog spider using scrapy-playwright.

Handles authentication and data extraction from Motus auto parts catalog.
Same platform as Alert (TopMotive) but with different credentials.
"""

import re
import random
from datetime import datetime
from typing import Generator, Any

import scrapy
from scrapy.http import Response, Request
from loguru import logger

from ..items import CatalogPartItem


class MotusSpider(scrapy.Spider):
    """
    Spider for Motus auto parts catalog (TopMotive platform).
    
    Uses scrapy-playwright for JavaScript rendering and anti-bot evasion.
    """
    
    name = "motus"
    allowed_domains = ["web1.carparts-cat.com", "carparts-cat.com"]
    
    # URLs
    LOGIN_URL = "https://web1.carparts-cat.com"
    BASE_URL = "https://web1.carparts-cat.com"
    
    custom_settings = {
        'PLAYWRIGHT_CONTEXTS': {
            'default': {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'locale': 'en-ZA',
                'timezone_id': 'Africa/Johannesburg',
            }
        }
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = self.settings.get('MOTUS_USERNAME', 'MWADEER')
        self.password = self.settings.get('MOTUS_PASSWORD', 'KGAv29')
        self.logged_in = False
        self.categories_scraped = 0
        self.parts_scraped = 0
    
    def start_requests(self) -> Generator[Request, None, None]:
        """Start with login page."""
        logger.info(f"Starting Motus spider with username: {self.username}")
        
        yield Request(
            url=self.LOGIN_URL,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_goto_kwargs": {
                    "wait_until": "networkidle",
                },
            },
            callback=self.parse_login,
            errback=self.errback,
            dont_filter=True,
        )
    
    async def parse_login(self, response: Response) -> Generator[Request, None, None]:
        """Handle login and navigate to catalog."""
        page = response.meta.get("playwright_page")
        
        if not page:
            logger.error("No Playwright page available")
            return
        
        try:
            # Check if already logged in
            if await self._is_logged_in(page):
                logger.info("Already logged in to Motus catalog")
                self.logged_in = True
                yield from await self._navigate_to_catalog(page, response)
                return
            
            # Find and fill login form
            logger.info("Attempting to login...")
            
            # Wait for page to be ready
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Try common username field selectors
            username_selectors = [
                '#txtUsername',
                '#username',
                '#UserName',
                'input[name="username"]',
                'input[name="txtUsername"]',
                'input[type="text"]:first-of-type',
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = await page.wait_for_selector(selector, timeout=5000)
                    if username_field:
                        logger.debug(f"Found username field: {selector}")
                        break
                except:
                    continue
            
            if not username_field:
                logger.error("Could not find username field")
                await page.screenshot(path='/tmp/motus_login_error.png')
                return
            
            # Fill username
            await username_field.fill(self.username)
            await page.wait_for_timeout(random.randint(500, 1500))
            
            # Find password field
            password_selectors = [
                '#txtPassword',
                '#password',
                '#Password',
                'input[name="password"]',
                'input[name="txtPassword"]',
                'input[type="password"]',
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = await page.wait_for_selector(selector, timeout=5000)
                    if password_field:
                        logger.debug(f"Found password field: {selector}")
                        break
                except:
                    continue
            
            if not password_field:
                logger.error("Could not find password field")
                await page.screenshot(path='/tmp/motus_login_error.png')
                return
            
            # Fill password
            await password_field.fill(self.password)
            await page.wait_for_timeout(random.randint(500, 1500))
            
            # Find and click login button
            login_selectors = [
                '#btnLogin',
                '#login',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Login")',
                'a:has-text("Login")',
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await page.wait_for_selector(selector, timeout=5000)
                    if login_button:
                        logger.debug(f"Found login button: {selector}")
                        break
                except:
                    continue
            
            if not login_button:
                logger.error("Could not find login button")
                await page.screenshot(path='/tmp/motus_login_error.png')
                return
            
            # Click login
            await login_button.click()
            await page.wait_for_load_state('networkidle', timeout=30000)
            await page.wait_for_timeout(random.randint(2000, 5000))
            
            # Verify login successful
            if await self._is_logged_in(page):
                self.logged_in = True
                logger.info("Successfully logged into Motus catalog")
                await page.screenshot(path='/tmp/motus_login_success.png')
                
                # Navigate to catalog and start scraping
                yield from await self._navigate_to_catalog(page, response)
            else:
                logger.error("Login failed for Motus catalog")
                await page.screenshot(path='/tmp/motus_login_failed.png')
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            await page.screenshot(path='/tmp/motus_login_exception.png')
        finally:
            pass
    
    async def _is_logged_in(self, page) -> bool:
        """Check if currently logged in."""
        try:
            logged_in_selectors = [
                'a:has-text("Logout")',
                'a:has-text("Log out")',
                'button:has-text("Logout")',
                '.user-menu',
                '#logout',
                'a[href*="logout"]',
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        return True
                except:
                    continue
            
            content_selectors = [
                '.product-list',
                '.category-list',
                '.catalog-content',
                '#catalog',
            ]
            
            for selector in content_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if element:
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
    async def _navigate_to_catalog(self, page, response: Response) -> Generator[Request, None, None]:
        """Navigate to catalog and start scraping categories."""
        current_url = page.url
        
        yield Request(
            url=current_url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_goto_kwargs": {
                    "wait_until": "networkidle",
                },
            },
            callback=self.parse_categories,
            errback=self.errback,
            dont_filter=True,
        )
    
    async def parse_categories(self, response: Response) -> Generator[Request, None, None]:
        """Extract and follow category links."""
        page = response.meta.get("playwright_page")
        
        if not page:
            logger.error("No Playwright page in parse_categories")
            return
        
        logger.info("Parsing categories...")
        
        category_selectors = [
            '.category-list a',
            '.nav-categories a',
            '#categories a',
            'a[href*="category"]',
            '.menu-item a',
            'a[href*="cat"]',
        ]
        
        categories = []
        
        for selector in category_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    logger.info(f"Found {len(elements)} potential category links with {selector}")
                    for elem in elements:
                        href = await elem.get_attribute('href')
                        text = await elem.inner_text()
                        if text.strip() and href:
                            if not href.startswith('http'):
                                href = self.BASE_URL + ('/' if not href.startswith('/') else '') + href
                            
                            skip_patterns = ['login', 'logout', 'register', 'contact', 'about', 'help']
                            if any(p in href.lower() for p in skip_patterns):
                                continue
                            
                            categories.append({
                                'name': text.strip(),
                                'url': href
                            })
                    if categories:
                        break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        seen_urls = set()
        unique_categories = []
        for cat in categories:
            if cat['url'] not in seen_urls:
                seen_urls.add(cat['url'])
                unique_categories.append(cat)
        
        self.categories_scraped = len(unique_categories)
        logger.info(f"Found {self.categories_scraped} unique categories")
        
        if not unique_categories:
            logger.warning("No categories found, attempting to extract products directly")
            yield from await self._extract_products_from_page(page, response, "All")
            return
        
        for cat in unique_categories[:5]:  # Limit for testing
            yield Request(
                url=cat['url'],
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
                    },
                    "category_name": cat['name'],
                },
                callback=self.parse_products,
                errback=self.errback,
            )
    
    async def parse_products(self, response: Response) -> Generator[Any, None, None]:
        """Extract products from a category page."""
        page = response.meta.get("playwright_page")
        category_name = response.meta.get("category_name", "Unknown")
        
        if not page:
            logger.error("No Playwright page in parse_products")
            return
        
        logger.info(f"Parsing products in category: {category_name}")
        
        async for item in self._extract_products_from_page(page, response, category_name):
            yield item
        
        has_next = await self._has_next_page(page)
        while has_next:
            await self._next_page(page)
            await page.wait_for_load_state('networkidle', timeout=30000)
            await page.wait_for_timeout(random.randint(2000, 5000))
            
            async for item in self._extract_products_from_page(page, response, category_name):
                yield item
            
            has_next = await self._has_next_page(page)
    
    async def _extract_products_from_page(self, page, response: Response, category_name: str):
        """Extract product items from current page."""
        product_selectors = [
            '.product-item',
            '.product-listing tr',
            '.parts-table tr',
            'tr[class*="product"]',
            'tr[class*="part"]',
            '.product-row',
            '.item-row',
        ]
        
        product_rows = []
        for selector in product_selectors:
            try:
                rows = await page.query_selector_all(selector)
                if rows and len(rows) > 0:
                    product_rows = rows
                    logger.debug(f"Found {len(rows)} product rows with {selector}")
                    break
            except:
                continue
        
        for row in product_rows:
            try:
                item = await self._extract_part_from_row(page, row, category_name)
                if item:
                    self.parts_scraped += 1
                    if self.parts_scraped % 50 == 0:
                        logger.info(f"Scraped {self.parts_scraped} parts so far...")
                    yield item
            except Exception as e:
                logger.debug(f"Error extracting part from row: {e}")
                continue
    
    async def _extract_part_from_row(self, page, row, category_name: str):
        """Extract a single part from a product row."""
        try:
            cells = await row.query_selector_all('td')
            if not cells:
                cells = await row.query_selector_all('div')
            
            if not cells:
                return None
            
            cell_texts = []
            for cell in cells:
                text = await cell.inner_text()
                cell_texts.append(text.strip())
            
            sku = None
            description = None
            brand = None
            oem_number = None
            cost_price = None
            retail_price = None
            stock_quantity = 0
            
            for text in cell_texts:
                text = text.strip()
                if not text:
                    continue
                
                if not sku and re.match(r'^[A-Z0-9][A-Z0-9\-\/]+$', text, re.IGNORECASE):
                    sku = text
                
                elif not retail_price and re.search(r'[R$€£]|[\d]+\.[\d]{2}', text):
                    price_str = re.sub(r'[^\d.]', '', text)
                    try:
                        retail_price = float(price_str) if price_str else None
                    except:
                        pass
                
                elif not brand:
                    brands = ['BOSCH', 'VALEO', 'HELLA', 'NGK', 'BREMBO', 'FAG', 'SKF', 'GATES', 'DAYCO', 'CONTINENTAL', 'MANN', 'MAHLE']
                    for b in brands:
                        if b in text.upper():
                            brand = text.title()
                            break
                
                elif not description and len(text) > 10:
                    description = text
            
            if sku or description:
                item = CatalogPartItem()
                item['sku'] = sku or f"MOTUS-{hash(description or '') % 1000000:06d}"
                item['supplier'] = 'motus'
                item['description'] = description
                item['category'] = category_name
                item['brand'] = brand
                item['oem_number'] = oem_number
                item['cost_price'] = cost_price
                item['retail_price'] = retail_price
                item['stock_quantity'] = stock_quantity
                item['scraped_at'] = datetime.now().isoformat()
                
                return item
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting part: {e}")
            return None
    
    async def _has_next_page(self, page) -> bool:
        """Check if there's a next page."""
        next_selectors = [
            'a.next',
            'a[rel="next"]',
            'a:has-text("Next")',
            '.pagination a:last-child:not(.disabled)',
        ]
        
        for selector in next_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    is_disabled = await elem.get_attribute('disabled')
                    class_name = await elem.get_attribute('class') or ''
                    if not is_disabled and 'disabled' not in class_name:
                        return True
            except:
                continue
        
        return False
    
    async def _next_page(self, page):
        """Click next page button."""
        next_selectors = [
            'a.next',
            'a[rel="next"]',
            'a:has-text("Next")',
            '.pagination a:last-child',
        ]
        
        for selector in next_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    await elem.click()
                    return
            except:
                continue
        
        logger.warning("Could not find next page button")
    
    async def errback(self, failure):
        """Handle request errors."""
        logger.error(f"Request failed: {failure.request.url}")
        logger.error(f"Error: {failure}")
