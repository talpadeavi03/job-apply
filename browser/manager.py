"""Playwright browser lifecycle and context manager for cloud execution."""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import LINKEDIN_LI_AT, NAUKRI_AT, NAUKRI_COOKIES, SCREENSHOTS_DIR

logger = logging.getLogger("aetherapply.browser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_EXTRA_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--disable-gpu",
]


class BrowserManager:
    """Manages a single Playwright Chromium instance across connector runs."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    def start(self) -> Browser:
        """Launches the shared Chromium browser."""
        if not self._playwright:
            self._playwright = sync_playwright().start()
        if not self._browser:
            logger.info("Launching Playwright Chromium (headless=%s)...", self.headless)
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=CHROMIUM_ARGS,
            )
        return self._browser

    def new_context(self, user_agent: Optional[str] = None) -> BrowserContext:
        """Creates an isolated browser context configured with stealth attributes."""
        browser = self.start()
        context = browser.new_context(
            user_agent=user_agent or DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            extra_http_headers=DEFAULT_EXTRA_HEADERS,
        )
        # Avoid webdriver flag detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Inject LinkedIn session cookie if configured
        if LINKEDIN_LI_AT:
            try:
                context.add_cookies([
                    {
                        "name": "li_at",
                        "value": LINKEDIN_LI_AT.strip(),
                        "domain": ".www.linkedin.com",
                        "path": "/",
                        "secure": True,
                        "httpOnly": True,
                    }
                ])
                logger.info("Injected LinkedIn session authentication cookie.")
            except Exception as e:
                logger.warning("Failed injecting LinkedIn cookie: %s", e)

        # Inject Naukri session cookies if configured
        if NAUKRI_AT or NAUKRI_COOKIES:
            try:
                cookies_to_add = []
                if NAUKRI_AT:
                    cookies_to_add.append({
                        "name": "nauk_at",
                        "value": NAUKRI_AT.strip(),
                        "domain": ".naukri.com",
                        "path": "/",
                    })
                if NAUKRI_COOKIES:
                    for item in NAUKRI_COOKIES.split(";"):
                        if "=" in item:
                            k, v = item.strip().split("=", 1)
                            cookies_to_add.append({
                                "name": k.strip(),
                                "value": v.strip(),
                                "domain": ".naukri.com",
                                "path": "/",
                            })
                if cookies_to_add:
                    context.add_cookies(cookies_to_add)
                    logger.info("Injected %d Naukri session cookies.", len(cookies_to_add))
            except Exception as e:
                logger.warning("Failed injecting Naukri cookies: %s", e)

        return context

    def take_screenshot(self, page: Page, name_prefix: str = "error") -> Path:
        """Captures page screenshot and saves it to screenshots directory."""
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{name_prefix}_{timestamp}.png"
        filepath = SCREENSHOTS_DIR / filename
        try:
            page.screenshot(path=str(filepath), full_page=True)
            logger.info("Saved screenshot to %s", filepath)
        except Exception as e:
            logger.warning("Failed to save screenshot: %s", e)
        return filepath

    def stop(self) -> None:
        """Gracefully closes browser and stops playwright."""
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping playwright: %s", e)
            self._playwright = None
        logger.info("Playwright session terminated.")

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
