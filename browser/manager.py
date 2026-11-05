"""Playwright browser lifecycle and context manager for cloud execution."""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import SCREENSHOTS_DIR

logger = logging.getLogger("aetherapply.browser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

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
        )
        # Avoid webdriver flag detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
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
