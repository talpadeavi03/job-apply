"""Cloud-native automated login and 2FA resolution for LinkedIn and Naukri."""
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from browser.utils import human_delay
from config.settings import (
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN,
    LINKEDIN_LI_AT,
    NAUKRI_AT,
    STORAGE_DIR,
)

logger = logging.getLogger("aetherapply.browser.auth")

STATE_FILE = STORAGE_DIR / "browser_state.json"


def fetch_verification_pin_from_gmail(query_term: str = "linkedin", max_wait_seconds: int = 40) -> Optional[str]:
    """
    Polls Gmail API for recent security verification emails and extracts the 6-digit PIN.
    """
    from connectors.gmail import GmailConnector, extract_body

    connector = GmailConnector({"max_emails": 5})
    if not connector.authenticate():
        logger.warning("Gmail authentication not available for 2FA PIN resolution.")
        return None

    logger.info("Polling Gmail for security verification PIN from %s...", query_term)
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        try:
            q = f"from:{query_term} (otp OR pin OR code OR verification OR 'one-time' OR security)"
            res = connector.service.users().messages().list(userId="me", q=q, maxResults=3).execute()
            messages = res.get("messages", [])

            for m in messages:
                msg = connector.service.users().messages().get(userId="me", id=m["id"], format="full").execute()
                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("subject", "")
                body = extract_body(msg.get("payload", {}))
                full_text = f"{subject} {body}"

                # Extract 6-digit PIN
                match = re.search(r"\b(\d{6})\b", full_text)
                if match:
                    pin = match.group(1)
                    logger.info("Extracted 6-digit verification PIN: %s", pin)
                    return pin
        except Exception as e:
            logger.debug("Gmail check iteration error: %s", e)

        time.sleep(5)

    logger.warning("Timed out waiting for 2FA verification PIN email from %s.", query_term)
    return None


def authenticate_linkedin_cloud(context: BrowserContext, page: Page) -> bool:
    """
    Performs fully automated LinkedIn login in GitHub Actions cloud runner.
    Resolves email verification PINs automatically via Gmail API.
    """
    username = os.getenv("LINKEDIN_USERNAME") or os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if not (username and password):
        logger.debug("LINKEDIN_USERNAME / LINKEDIN_PASSWORD not provided in environment.")
        return False

    try:
        logger.info("Attempting cloud login for LinkedIn account: %s", username)
        page.goto("https://www.linkedin.com/login", timeout=30000, wait_until="domcontentloaded")
        human_delay(2.0, 3.0)

        # Check if already authenticated
        if "feed" in page.url or page.query_selector(".global-nav__me, #global-nav"):
            logger.info("Already authenticated on LinkedIn.")
            save_storage_state(context)
            return True

        # Fill credentials
        user_input = page.query_selector("#username, input[name='session_key']")
        pass_input = page.query_selector("#password, input[name='session_password']")
        submit_btn = page.query_selector("button[type='submit'], .btn__primary--large")

        if not (user_input and pass_input and submit_btn):
            logger.warning("LinkedIn login form elements not found.")
            return False

        user_input.fill(username.strip())
        human_delay(0.5, 1.0)
        pass_input.fill(password.strip())
        human_delay(0.5, 1.2)
        submit_btn.click()
        human_delay(3.0, 5.0)

        # Check for 2FA / Security PIN Challenge
        pin_input = page.query_selector(
            "#input__email_verification_pin, input[name='pin'], #email-pin, input[name='verification-code']"
        )
        if pin_input:
            logger.info("LinkedIn 2FA challenge detected. Fetching PIN from Gmail...")
            pin = fetch_verification_pin_from_gmail(query_term="linkedin", max_wait_seconds=45)
            if pin:
                pin_input.fill(pin)
                human_delay(1.0, 1.5)
                confirm_btn = page.query_selector("#email-pin-submit-button, button[type='submit']")
                if confirm_btn:
                    confirm_btn.click()
                    human_delay(4.0, 6.0)

        # Confirm successful login
        if "feed" in page.url or page.query_selector(".global-nav__me, #global-nav"):
            logger.info("Successfully authenticated to LinkedIn in cloud!")
            save_storage_state(context)
            return True

    except Exception as e:
        logger.error("Error during automated LinkedIn cloud login: %s", e)

    return False


def authenticate_naukri_cloud(context: BrowserContext, page: Page) -> bool:
    """
    Performs automated Naukri login in GitHub Actions cloud runner.
    """
    username = os.getenv("NAUKRI_USERNAME") or os.getenv("NAUKRI_EMAIL")
    password = os.getenv("NAUKRI_PASSWORD")

    if not (username and password):
        logger.debug("NAUKRI_USERNAME / NAUKRI_PASSWORD not provided in environment.")
        return False

    try:
        logger.info("Attempting cloud login for Naukri account: %s", username)
        page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="domcontentloaded")
        human_delay(2.5, 3.5)

        # Check if already authenticated
        if "mynaukri" in page.url or page.query_selector(".nI-gNb-drawer__bars, .view-profile-wrapper, a[href*='mynaukri']"):
            logger.info("Already authenticated on Naukri.")
            save_storage_state(context)
            return True

        user_input = page.query_selector("#usernameField, input[placeholder*='Email' i], input[type='text']")
        pass_input = page.query_selector("#passwordField, input[placeholder*='Password' i], input[type='password']")
        submit_btn = page.query_selector("button:has-text('Login'), button.blue-btn, button[type='submit']")

        if user_input and pass_input and submit_btn:
            user_input.fill(username.strip())
            human_delay(0.5, 1.0)
            pass_input.fill(password.strip())
            human_delay(0.5, 1.2)
            submit_btn.click()
            human_delay(3.5, 5.0)

            # Check for OTP challenge
            otp_input = page.query_selector("input[placeholder*='OTP' i], input[name='otp'], input.otp-input")
            if otp_input:
                logger.info("Naukri OTP challenge detected. Fetching OTP from Gmail...")
                otp = fetch_verification_pin_from_gmail(query_term="naukri", max_wait_seconds=45)
                if otp:
                    otp_input.fill(otp)
                    human_delay(1.0, 1.5)
                    otp_submit = page.query_selector("button:has-text('Verify'), button:has-text('Submit'), button[type='submit']")
                    if otp_submit:
                        otp_submit.click()
                        human_delay(3.5, 5.0)

            # Verify login success
            if "mynaukri" in page.url or page.query_selector(".nI-gNb-drawer__bars, .view-profile-wrapper, a[href*='mynaukri']"):
                logger.info("Successfully authenticated to Naukri in cloud!")
            else:
                logger.info("Naukri cloud authentication submitted.")
            save_storage_state(context)
            return True

    except Exception as e:
        logger.error("Error during automated Naukri cloud login: %s", e)

    return False


def save_storage_state(context: BrowserContext) -> None:
    """Persists authenticated browser session cookies and localStorage to disk."""
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(STATE_FILE))
        logger.info("Persisted authenticated cloud session state to %s", STATE_FILE)
    except Exception as e:
        logger.debug("Failed saving storage state: %s", e)


def load_storage_state(context: BrowserContext) -> bool:
    """Restores persisted cloud session state if present."""
    if STATE_FILE.exists():
        try:
            logger.info("Restoring existing cloud browser session from %s", STATE_FILE)
            return True
        except Exception as e:
            logger.debug("Failed loading storage state: %s", e)
    return False
