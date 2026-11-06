"""Playwright browser lifecycle and context manager for cloud execution."""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import LINKEDIN_LI_AT, NAUKRI_AT, NAUKRI_COOKIES, SCREENSHOTS_DIR, STORAGE_DIR

logger = logging.getLogger("aetherapply.browser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_EXTRA_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Google Chrome";v="130", "Chromium";v="130", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
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


def check_linkedin_cookie_validity(token: str) -> bool:
    """Checks if the LinkedIn session cookie is valid or revoked before injecting."""
    try:
        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        s.cookies.set("li_at", token.strip(), domain=".linkedin.com")
        r = s.get("https://www.linkedin.com/feed/", allow_redirects=False, timeout=4)
        set_cookie = r.headers.get("Set-Cookie", "")
        if "delete me" in set_cookie or "deleted" in set_cookie:
            return False
        if r.status_code == 302 and r.headers.get("Location") == "https://www.linkedin.com/feed/":
            return False
        return True
    except Exception:
        return False


class BrowserManager:
    """Manages a single Playwright Chromium instance across connector runs."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._linkedin_cookie_valid: Optional[bool] = None

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
        state_file = STORAGE_DIR / "browser_state.json"
        storage_kwargs = {"storage_state": str(state_file)} if state_file.exists() else {}

        context = browser.new_context(
            user_agent=user_agent or DEFAULT_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            extra_http_headers=DEFAULT_EXTRA_HEADERS,
            **storage_kwargs,
        )
        # Avoid webdriver flag detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Inject LinkedIn session cookie if configured and valid
        if LINKEDIN_LI_AT:
            try:
                li_val = LINKEDIN_LI_AT.strip()
                if self._linkedin_cookie_valid is None:
                    self._linkedin_cookie_valid = check_linkedin_cookie_validity(li_val)

                if self._linkedin_cookie_valid:
                    context.add_cookies([
                        {
                            "name": "li_at",
                            "value": li_val,
                            "domain": ".linkedin.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": True,
                        },
                        {
                            "name": "li_at",
                            "value": li_val,
                            "domain": ".www.linkedin.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": True,
                        },
                    ])
                    logger.info("Injected valid LinkedIn session authentication cookie.")
                else:
                    logger.warning("LinkedIn session cookie is invalid or expired. Skipping cookie injection to avoid redirect loops.")
            except Exception as e:
                logger.warning("Failed injecting LinkedIn cookie: %s", e)

        # Inject Naukri session cookies if configured
        if NAUKRI_AT:
            try:
                token_val = NAUKRI_AT.strip()
                context.add_cookies([
                    {
                        "name": "nauk_at",
                        "value": token_val,
                        "domain": ".naukri.com",
                        "path": "/",
                    },
                    {
                        "name": "_naukri_user",
                        "value": token_val,
                        "domain": ".naukri.com",
                        "path": "/",
                    },
                ])
                # Set in localStorage for Next.js / client-side React session
                context.add_init_script(f"""
                    try {{
                        localStorage.setItem('accessToken', '{token_val}');
                        localStorage.setItem('nauk_at', '{token_val}');
                    }} catch (e) {{}}
                """)
                logger.info("Injected Naukri JWT session tokens.")
            except Exception as e:
                logger.warning("Failed injecting Naukri tokens: %s", e)
        elif NAUKRI_COOKIES:
            try:
                cookies_to_add = []
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
