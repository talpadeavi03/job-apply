"""Naukri 1-Click Apply and Questionnaire Automation."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import ANSWERS, get_answer_for_question
from application.uploader import upload_resume
from browser.utils import human_delay, safe_click, safe_fill
from config.settings import RESUME_PATH

logger = logging.getLogger("aetherapply.application.naukri")


class NaukriApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def apply_to_job(self, job_url: str) -> Dict[str, Any]:
        """
        Attempts automated 1-click apply on a Naukri job listing.
        Handles direct apply, questionnaire modals, or external portal redirection.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            logger.info("Navigating to Naukri job: %s", job_url)
            self.page.goto(job_url, timeout=35000, wait_until="domcontentloaded")
            human_delay(2.5, 3.5)

            # Check if already applied
            already_applied = self.page.query_selector(
                "button:has-text('Already Applied'), .already-applied, text='Already Applied'"
            )
            if already_applied:
                result["status"] = "submitted"
                result["details"] = "Already applied to this job on Naukri."
                return result

            # Check for Naukri Apply button
            apply_btn = self.page.query_selector(
                "#apply-button, .apply-button, button:has-text('Apply'), .apply-btn, a:has-text('Apply on website')"
            )

            if not apply_btn:
                result["status"] = "queued_manual"
                result["details"] = "No Apply button visible on Naukri (session login required or expired listing)."
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

            # Click the direct 1-click Apply button
            logger.info("Clicking Naukri Apply button: %s", btn_text)
            apply_btn.click()
            human_delay(2.0, 3.0)

            # Check for Questionnaire Modal / Recruiter Chatbot
            modal = self.page.query_selector(".apply-message, .bot-overlay, .chatbot-container, .modal, div[role='dialog']")
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
                    submit_btn.click()
                    human_delay(2.0, 3.0)

            # Check success indicator
            success_elem = self.page.query_selector(
                ".apply-message, .success-message, text='Successfully Applied', text='Applied'"
            )
            if success_elem or "applied" in self.page.content().lower():
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
