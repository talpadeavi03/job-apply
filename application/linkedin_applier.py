"""LinkedIn Easy Apply automation handler."""
import logging
from pathlib import Path
from typing import Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import get_answer_for_question
from application.uploader import upload_resume
from browser.utils import human_delay, safe_click, safe_fill

logger = logging.getLogger("aetherapply.application.linkedin")


class LinkedInApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path

    def apply_to_job(self, job_url: str) -> Dict[str, any]:
        """
        Attempts LinkedIn Easy Apply for a given job URL.
        Returns dict with status ('submitted', 'queued_manual', 'failed') and details.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            logger.info("Navigating to LinkedIn job: %s", job_url)
            self.page.goto(job_url, timeout=30000, wait_until="domcontentloaded")
            human_delay(2.0, 3.5)

            # Check for Easy Apply button
            apply_btn = self.page.query_selector(
                "button.jobs-apply-button, .jobs-apply-button--top-card button, button[aria-label*='Easy Apply']"
            )

            if not apply_btn:
                # External apply link or requires login
                external_btn = self.page.query_selector("a[href*='apply'], button:has-text('Apply')")
                if external_btn:
                    result["status"] = "queued_manual"
                    result["details"] = "External company application link (manual apply required)."
                else:
                    result["status"] = "queued_manual"
                    result["details"] = "No Easy Apply button visible (authentication required or posting expired)."
                return result

            # Click Easy Apply
            apply_btn.click()
            human_delay(1.5, 2.5)

            # Modal interaction loop (up to 5 steps)
            for step in range(5):
                # 1. Fill visible text/number inputs
                inputs = self.page.query_selector_all(".jobs-easy-apply-modal input[type='text'], .jobs-easy-apply-modal input[type='tel']")
                for inp in inputs:
                    val = inp.input_value()
                    if not val:
                        # Determine question from label or aria-label
                        aria = inp.get_attribute("aria-label") or ""
                        ans = get_answer_for_question(aria) or "3.5"
                        inp.fill(ans)

                # 2. Check for Resume upload
                upload_resume(self.page, self.resume_path, selector=".jobs-easy-apply-modal input[type='file']")

                # 3. Look for Next, Review, or Submit buttons
                submit_btn = self.page.query_selector(".jobs-easy-apply-modal button[aria-label*='Submit application']")
                if submit_btn:
                    logger.info("Reached Submit step on LinkedIn Easy Apply.")
                    human_delay(1.0, 2.0)
                    submit_btn.click()
                    human_delay(2.0, 3.0)
                    result["status"] = "submitted"
                    result["details"] = "Successfully submitted via LinkedIn Easy Apply."
                    return result

                review_btn = self.page.query_selector(".jobs-easy-apply-modal button[aria-label*='Review your application']")
                if review_btn:
                    review_btn.click()
                    human_delay(1.5, 2.5)
                    continue

                next_btn = self.page.query_selector(".jobs-easy-apply-modal button[aria-label*='Continue to next step']")
                if next_btn:
                    next_btn.click()
                    human_delay(1.5, 2.5)
                else:
                    # Unrecognized step or complex custom form
                    result["status"] = "queued_manual"
                    result["details"] = f"Complex custom questions at step {step + 1}; queued for manual review."
                    break

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Navigation timeout"
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during LinkedIn apply: %s", e)

        return result
