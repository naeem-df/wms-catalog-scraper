"""
Authentication module for TopMotive platform.

Handles login and session management for Alert and Motus catalogs.
"""

import os
import random
from typing import Optional, Tuple
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from loguru import logger


# Credentials from environment
ALERT_USERNAME = os.getenv("ALERT_USERNAME", "MMOIABK")
ALERT_PASSWORD = os.getenv("ALERT_PASSWORD", "RMVW1")
MOTUS_USERNAME = os.getenv("MOTUS_USERNAME", "MWADEER")
MOTUS_PASSWORD = os.getenv("MOTUS_PASSWORD", "KGAv29")

# URLs
ALERT_URL = "https://web1.carparts-cat.com/default.aspx?10=7FD0A9CE5E4D41DEACA81956B6408394494004&14=4&12=1003"
MOTUS_URL = "https://web1.carparts-cat.com"


class AuthSession:
    """Manages authentication session for TopMotive catalogs."""
    
    def __init__(self, supplier: str, headless: bool = True):
        """
        Initialize auth session.
        
        Args:
            supplier: 'alert' or 'motus'
            headless: Run browser in headless mode
        """
        self.supplier = supplier.lower()
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Set credentials based on supplier
        if self.supplier == "alert":
            self.username = ALERT_USERNAME
            self.password = ALERT_PASSWORD
            self.login_url = ALERT_URL
        elif self.supplier == "motus":
            self.username = MOTUS_USERNAME
            self.password = MOTUS_PASSWORD
            self.login_url = MOTUS_URL
        else:
            raise ValueError(f"Unknown supplier: {supplier}")
        
        # Cookie storage path
        self.cookie_path = Path(f"/tmp/wms_scraper_{supplier}_cookies.json")
    
    async def start(self) -> Page:
        """Start browser and create page with stealth mode."""
        playwright = await async_playwright().start()
        
        # Launch browser with anti-detection settings
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='en-ZA',
            timezone_id='Africa/Johannesburg',
        )
        
        # Add stealth scripts
        await self.context.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-ZA', 'en', 'en-US']
            });
            
            // Hide automation
            window.chrome = {
                runtime: {}
            };
        """)
        
        # Load cookies if they exist
        if self.cookie_path.exists():
            try:
                import json
                cookies = json.loads(self.cookie_path.read_text())
                await self.context.add_cookies(cookies)
                logger.info(f"Loaded saved cookies for {self.supplier}")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")
        
        self.page = await self.context.new_page()
        
        # Random delay to look human
        await self._random_delay()
        
        return self.page
    
    async def login(self) -> bool:
        """
        Perform login to TopMotive platform.
        
        Returns:
            True if login successful, False otherwise
        """
        if not self.page:
            await self.start()
        
        logger.info(f"Logging into {self.supplier} catalog...")
        
        try:
            # Navigate to login URL
            await self.page.goto(self.login_url, wait_until='networkidle', timeout=60000)
            await self._random_delay()
            
            # Check if already logged in (look for logout button or user menu)
            if await self._is_logged_in():
                logger.info(f"Already logged in to {self.supplier}")
                return True
            
            # Find and fill username field
            # TopMotive uses various field IDs - try common ones
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
                    username_field = await self.page.wait_for_selector(selector, timeout=5000)
                    if username_field:
                        break
                except:
                    continue
            
            if not username_field:
                logger.error("Could not find username field")
                # Take screenshot for debugging
                await self.page.screenshot(path=f'/tmp/{self.supplier}_login_error.png')
                return False
            
            # Fill username
            await username_field.fill(self.username)
            await self._random_delay(0.5, 1.5)
            
            # Find and fill password field
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
                    password_field = await self.page.wait_for_selector(selector, timeout=5000)
                    if password_field:
                        break
                except:
                    continue
            
            if not password_field:
                logger.error("Could not find password field")
                await self.page.screenshot(path=f'/tmp/{self.supplier}_login_error.png')
                return False
            
            # Fill password
            await password_field.fill(self.password)
            await self._random_delay(0.5, 1.5)
            
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
                    login_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if login_button:
                        break
                except:
                    continue
            
            if not login_button:
                logger.error("Could not find login button")
                await self.page.screenshot(path=f'/tmp/{self.supplier}_login_error.png')
                return False
            
            # Click login
            await login_button.click()
            
            # Wait for navigation
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self._random_delay()
            
            # Verify login successful
            if await self._is_logged_in():
                logger.info(f"Successfully logged into {self.supplier}")
                
                # Save cookies
                await self._save_cookies()
                
                return True
            else:
                logger.error(f"Login failed for {self.supplier}")
                await self.page.screenshot(path=f'/tmp/{self.supplier}_login_failed.png')
                return False
                
        except Exception as e:
            logger.error(f"Login error for {self.supplier}: {e}")
            if self.page:
                await self.page.screenshot(path=f'/tmp/{self.supplier}_login_exception.png')
            return False
    
    async def _is_logged_in(self) -> bool:
        """Check if already logged in."""
        try:
            # Look for elements that indicate logged-in state
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
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        return True
                except:
                    continue
            
            # Check if we're on a page that requires login (product listings, etc.)
            # If we see category/product elements, we're logged in
            content_indicators = [
                '.product-list',
                '.category-list',
                '.catalog-content',
                '#catalog',
            ]
            
            for selector in content_indicators:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        return True
                except:
                    continue
            
            return False
            
        except Exception:
            return False
    
    async def _save_cookies(self):
        """Save cookies to file for persistence."""
        try:
            import json
            cookies = await self.context.cookies()
            self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
            self.cookie_path.write_text(json.dumps(cookies))
            logger.info(f"Saved cookies for {self.supplier}")
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")
    
    async def _random_delay(self, min_seconds: float = None, max_seconds: float = None):
        """Add random delay to appear human-like."""
        min_s = min_seconds or float(os.getenv("SCRAPER_DELAY_MIN", "2"))
        max_s = max_seconds or float(os.getenv("SCRAPER_DELAY_MAX", "5"))
        
        delay = random.uniform(min_s, max_s)
        await self.page.wait_for_timeout(int(delay * 1000))
    
    async def close(self):
        """Close browser session."""
        if self.browser:
            await self.browser.close()
            logger.info(f"Closed browser for {self.supplier}")


async def create_authenticated_session(supplier: str, headless: bool = True) -> Tuple[AuthSession, Page]:
        """
        Get authenticated page, logging in if necessary.
        
        Returns:
            Authenticated Page object
        """
        if not self.page:
            await self.start()
        
        # Check if logged in
        if not await self._is_logged_in():
            success = await self.login()
            if not success:
                raise RuntimeError(f"Failed to authenticate to {self.supplier}")
        
        return self.page
    
    async def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info(f"Closed {self.supplier} browser session")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
