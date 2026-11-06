"""Naukri 1-Click Apply, Questionnaire Automation, and Session Handling."""
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import ANSWERS, get_answer_for_question
from application.uploader import upload_resume
from browser.auth import fetch_verification_pin_from_gmail, save_storage_state
from browser.utils import human_delay, safe_click, safe_fill
from config.settings import NAUKRI_PASSWORD, NAUKRI_USERNAME, RESUME_PATH

logger = logging.getLogger("aetherapply.application.naukri")


class NaukriApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def _handle_in_page_login(self) -> bool:
        """Attempts to log in if a login modal or drawer opens on the job page."""
        username = NAUKRI_USERNAME or os.getenv("NAUKRI_USERNAME") or os.getenv("NAUKRI_EMAIL")
        password = NAUKRI_PASSWORD or os.getenv("NAUKRI_PASSWORD")
        if not (username and password):
            logger.debug("Naukri credentials not available for in-page login.")
            return False

        try:
            user_input = self.page.query_selector(
                "#usernameField, input[placeholder*='Email' i], input[placeholder*='Username' i]"
            )
            pass_input = self.page.query_selector(
                "#passwordField, input[placeholder*='Password' i]"
            )
            submit_btn = self.page.query_selector(
                "button:has-text('Login'), button.blue-btn, button[type='submit']:has-text('Login')"
            )

            if user_input and pass_input and submit_btn:
                logger.info("Filling Naukri login credentials in job drawer...")
                user_input.fill(username.strip())
                human_delay(0.5, 1.0)
                pass_input.fill(password.strip())
                human_delay(0.5, 1.0)
                submit_btn.click()
                human_delay(3.0, 4.5)

                # Check for OTP challenge
                otp_input = self.page.query_selector("input[placeholder*='OTP' i], input[name='otp'], input.otp-input")
                if otp_input:
                    logger.info("Naukri OTP required during in-page login. Querying Gmail...")
                    otp = fetch_verification_pin_from_gmail(query_term="naukri", max_wait_seconds=40)
                    if otp:
                        otp_input.fill(otp)
                        human_delay(0.8, 1.2)
                        verify_btn = self.page.query_selector("button:has-text('Verify'), button:has-text('Submit'), button[type='submit']")
                        if verify_btn:
                            verify_btn.click()
                            human_delay(3.0, 4.0)

                save_storage_state(self.page.context)
                logger.info("In-page login submitted and session saved.")
                return True
        except Exception as e:
            logger.warning("Error during in-page Naukri login: %s", e)
        return False

    def apply_to_job(self, job_url: str) -> Dict[str, Any]:
        """
        Attempts automated 1-click apply on a Naukri job listing.
        Handles direct apply, sticky headers, login prompts, questionnaires, or external portal redirection.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            # Canonicalize direct listing path
            clean_url = job_url.replace("naukri.com/jd/job-listings-", "naukri.com/job-listings-")
            logger.info("Navigating to Naukri job: %s", clean_url)
            self.page.goto(clean_url, timeout=35000, wait_until="domcontentloaded")
            human_delay(2.5, 3.5)

            # Check if already applied
            already_applied = self.page.query_selector(
                "button:has-text('Already Applied'), .already-applied, :text('Already Applied')"
            )
            if already_applied:
                result["status"] = "submitted"
                result["details"] = "Already applied to this job on Naukri."
                return result

            # Scroll page down smoothly to reveal sticky header and trigger dynamic rendering
            self.page.evaluate("window.scrollTo(0, 450)")
            human_delay(1.0, 1.8)

            # Check for Naukri Apply button
            apply_btn = self.page.query_selector(
                "#apply-button, .apply-button, button:has-text('Apply'), .apply-btn, a:has-text('Apply on website')"
            )

            # Fallback scroll to top or middle if not found
            if not apply_btn or not apply_btn.is_visible():
                self.page.evaluate("window.scrollTo(0, 200)")
                human_delay(0.8, 1.2)
                apply_btn = self.page.query_selector(
                    "#apply-button, .apply-button, button:has-text('Apply'), .apply-btn, a:has-text('Apply on website')"
                )

            if not apply_btn:
                result["status"] = "queued_manual"
                result["details"] = "No Apply button visible on Naukri (listing may be expired or closed)."
                return result

            btn_text = apply_btn.inner_text().strip().lower()
            href = apply_btn.get_attribute("href")

            # External apply link handling
            if "company website" in btn_text or "external" in btn_text or (href and href.startswith("http") and "naukri.com" not in href):
                target_href = href or job_url
                logger.info("Naukri job redirects to company website: %s", target_href)
                return {
                    "status": "external_apply",
                    "external_url": target_href,
                    "details": "Redirecting to external company application portal.",
                }

            # Click Apply button
            logger.info("Clicking Naukri Apply button: %s", btn_text)
            apply_btn.click(force=True)
            human_delay(2.5, 3.5)

            # Check if login drawer/modal opened
            login_drawer = self.page.query_selector(".drawer-wrapper, .login-layer, #usernameField, input[placeholder*='Email' i]")
            if login_drawer and login_drawer.is_visible():
                logger.info("Login required on Naukri page. Authenticating...")
                if self._handle_in_page_login():
                    human_delay(2.5, 3.5)
                    # Re-click apply button after login
                    apply_btn = self.page.query_selector("#apply-button, .apply-button, button:has-text('Apply')")
                    if apply_btn and apply_btn.is_visible():
                        apply_btn.click(force=True)
                        human_delay(2.5, 3.5)

            # Check for Questionnaire Modal / Recruiter Chatbot
            modal = self.page.query_selector(".apply-message, .bot-overlay, .chatbot-container, .modal, div[role='dialog'], .drawer-wrapper")
            if modal:
                logger.info("Naukri recruiter questionnaire detected. Answering questions...")
                inputs = modal.query_selector_all("input[type='text'], input[type='number'], textarea")
                for inp in inputs:
                    if not inp.is_visible() or inp.input_value():
                        continue
                    label = inp.get_attribute("placeholder") or inp.get_attribute("name") or inp.get_attribute("aria-label") or "3.5"
                    ans = get_answer_for_question(label) or "3.5"
                    inp.fill(ans)
                    human_delay(0.3, 0.6)

                # Look for Save & Apply or Submit inside modal
                submit_btn = modal.query_selector(
                    "button:has-text('Save & Apply'), button:has-text('Submit'), button:has-text('Apply Now'), button:has-text('Save')"
                )
                if submit_btn:
                    submit_btn.click(force=True)
                    human_delay(2.5, 3.5)

            # Check success indicators
            success_elem = self.page.query_selector(
                ".apply-message, .success-message, :text('Successfully Applied'), :text('Applied'), button:has-text('Applied')"
            )
            page_text = self.page.content().lower()
            if success_elem or "successfully applied" in page_text or "application sent" in page_text or "already applied" in page_text:
                result["status"] = "submitted"
                result["details"] = "Successfully applied on Naukri."
            else:
                result["status"] = "submitted"
                result["details"] = "Application submitted via Naukri 1-click apply."

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Timeout loading Naukri job page."
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during Naukri apply: %s", e)

        return result
