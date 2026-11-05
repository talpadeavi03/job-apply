"""Browser module for Playwright automation."""
from browser.manager import BrowserManager
from browser.utils import human_delay, safe_click, safe_fill, safe_goto

__all__ = ["BrowserManager", "human_delay", "safe_click", "safe_fill", "safe_goto"]
