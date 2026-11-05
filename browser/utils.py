"""Helper functions for safe, human-like browser interactions."""
import logging
import random
import time
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("aetherapply.browser.utils")


def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Sleeps for a random duration between min and max seconds to emulate human behavior."""
    sleep_time = random.uniform(min_seconds, max_seconds)
    time.sleep(sleep_time)


def safe_goto(page: Page, url: str, timeout: int = 30000, wait_until: str = "domcontentloaded") -> bool:
    """Navigates to URL with timeout and error handling."""
    try:
        page.goto(url, timeout=timeout, wait_until=wait_until)
        human_delay(1.5, 2.5)
        return True
    except PlaywrightTimeoutError:
        logger.warning("Timeout navigating to %s", url)
        return False
    except Exception as e:
        logger.warning("Error navigating to %s: %s", url, e)
        return False


def safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    """Clicks an element safely with human delay."""
    try:
        element = page.wait_for_selector(selector, state="visible", timeout=timeout)
        if element:
            human_delay(0.5, 1.2)
            element.click()
            human_delay(0.5, 1.0)
            return True
        return False
    except Exception as e:
        logger.debug("Failed to click %s: %s", selector, e)
        return False


def safe_fill(page: Page, selector: str, text: str, timeout: int = 5000) -> bool:
    """Fills an input field with simulated typing delay."""
    try:
        element = page.wait_for_selector(selector, state="visible", timeout=timeout)
        if element:
            element.click()
            element.fill("")
            human_delay(0.2, 0.5)
            element.type(text, delay=random.randint(50, 120))
            return True
        return False
    except Exception as e:
        logger.debug("Failed to fill %s: %s", selector, e)
        return False
