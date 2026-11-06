"""LinkedIn Easy Apply and External Apply automation handler."""
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import ANSWERS, get_answer_for_question
from application.uploader import upload_resume
from browser.utils import human_delay, safe_click, safe_fill
from config.settings import RESUME_PATH
from engine.dedup import canonicalize_job_url
from mcp_server.ai_agent import answer_form_question, generate_ai_answer

logger = logging.getLogger("aetherapply.application.linkedin")


class LinkedInApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def apply_to_job(self, job_url: str, job_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempts LinkedIn Easy Apply or extracts external career portal URL.
        Returns dict with status ('submitted', 'external_apply', 'queued_manual', 'failed') and details.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        target_url = canonicalize_job_url(job_url) or job_url

        try:
            logger.info("Navigating to LinkedIn job: %s", target_url)
            self.page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            human_delay(2.5, 3.5)

            # Check if there is an Easy Apply button
            easy_apply_btn = self.page.query_selector(
                "button[aria-label*='Easy Apply' i], button:has-text('Easy Apply'), "
                "span:has-text('Easy Apply'), button.jobs-apply-button"
            )

            # If no Easy Apply, check for external application link
            if not easy_apply_btn:
                external_btn = self.page.query_selector(
                    "a.jobs-apply-button, a[aria-label*='Apply on company website' i], "
                    "a:has-text('Apply'), button:has-text('Apply on company website')"
                )
                if external_btn:
                    href = external_btn.get_attribute("href")
                    if href:
                        # Extract real destination if wrapped in LinkedIn safety redirect
                        if "linkedin.com/safety/go" in href or "url=" in href:
                            parsed = urllib.parse.urlparse(href)
                            qs = urllib.parse.parse_qs(parsed.query)
                            if "url" in qs and qs["url"]:
                                href = urllib.parse.unquote(qs["url"][0])

                        logger.info("Detected external LinkedIn apply URL: %s", href)
                        return {
                            "status": "external_apply",
                            "external_url": href,
                            "details": "Redirecting to external company application portal.",
                        }

                result["status"] = "queued_manual"
                result["details"] = "No Easy Apply or external link available on LinkedIn job posting."
                return result

            # Click Easy Apply button
            logger.info("Clicking LinkedIn Easy Apply button...")
            easy_apply_btn.click()
            human_delay(2.0, 3.0)

            # Step through modal steps (up to 8 steps)
            for step in range(8):
                modal = self.page.query_selector(".jobs-easy-apply-modal, div[role='dialog'], .artdeco-modal")
                if not modal:
                    logger.debug("Modal not detected at step %d", step + 1)
                    break

                # 1. Fill visible inputs (text, number, tel, email)
                inputs = modal.query_selector_all("input[type='text'], input[type='number'], input[type='tel'], input[type='email']")
                for inp in inputs:
                    try:
                        if not inp.is_visible() or inp.input_value():
                            continue
                        # Determine context from placeholder, aria-label, or label
                        context_str = " ".join(filter(None, [
                            inp.get_attribute("aria-label") or "",
                            inp.get_attribute("placeholder") or "",
                            inp.get_attribute("name") or "",
                        ]))
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            lbl = modal.query_selector(f"label[for='{inp_id}']")
                            if lbl:
                                context_str += " " + lbl.inner_text()

                        inp_type = inp.get_attribute("type") or "text"
                        ans = answer_form_question(context_str, field_type=inp_type, job_title=job_title)
                        inp.fill(ans)
                        human_delay(0.2, 0.4)
                    except Exception as inp_err:
                        logger.debug("Input fill error: %s", inp_err)

                # 1b. Fill open-ended textareas using Gemini MCP reasoning
                textareas = modal.query_selector_all("textarea")
                for ta in textareas:
                    try:
                        if not ta.is_visible() or ta.input_value():
                            continue
                        context_str = " ".join(filter(None, [
                            ta.get_attribute("aria-label") or "",
                            ta.get_attribute("placeholder") or "",
                            ta.get_attribute("name") or "",
                        ]))
                        ta_id = ta.get_attribute("id")
                        if ta_id:
                            lbl = modal.query_selector(f"label[for='{ta_id}']")
                            if lbl:
                                context_str += " " + lbl.inner_text()
                        if not context_str.strip():
                            context_str = f"Why are you a strong fit for the {job_title or 'Cloud Engineer'} role?"

                        ai_ans = answer_form_question(context_str, field_type="textarea", job_title=job_title)
                        ta.fill(ai_ans)
                        human_delay(0.3, 0.6)
                    except Exception as ta_err:
                        logger.debug("Textarea fill error: %s", ta_err)

                # 2. Select Radio buttons (e.g. Work authorization -> Yes, Visa sponsorship -> No)
                fieldsets = modal.query_selector_all("fieldset")
                for fs in fieldsets:
                    try:
                        legend = fs.query_selector("legend")
                        leg_text = legend.inner_text().lower() if legend else ""
                        if any(q in leg_text for q in ["sponsorship", "require visa", "visa sponsorship"]):
                            no_radio = fs.query_selector("label:has-text('No'), input[value*='No' i], input[id*='no' i]")
                            if no_radio:
                                no_radio.click()
                        else:
                            yes_radio = fs.query_selector("label:has-text('Yes'), input[value*='Yes' i], input[id*='yes' i]")
                            if yes_radio:
                                yes_radio.click()
                    except Exception as fs_err:
                        logger.debug("Fieldset radio selection error: %s", fs_err)

                # 3. Handle Select Dropdowns
                selects = modal.query_selector_all("select")
                for sel in selects:
                    try:
                        val = sel.input_value()
                        if not val or val == "Select an option":
                            options = sel.query_selector_all("option")
                            for opt in options:
                                opt_val = opt.get_attribute("value") or ""
                                opt_text = opt.inner_text().strip().lower()
                                if opt_val and opt_val != "Select an option" and opt_text != "select an option":
                                    sel.select_option(value=opt_val)
                                    break
                    except Exception as sel_err:
                        logger.debug("Select dropdown error: %s", sel_err)

                # 4. Attach Resume if file input present
                upload_resume(self.page, self.resume_path, selector=".jobs-easy-apply-modal input[type='file'], div[role='dialog'] input[type='file']")

                # 5. Look for Submit button
                submit_btn = modal.query_selector(
                    "button[aria-label*='Submit application' i], button:has-text('Submit application'), button:has-text('Submit')"
                )
                if submit_btn:
                    logger.info("Found Submit Application button on step %d. Submitting...", step + 1)
                    human_delay(1.0, 2.0)
                    submit_btn.click()
                    human_delay(2.5, 3.5)

                    # Dismiss confirmation / feedback modal
                    dismiss_btn = self.page.query_selector("button[aria-label='Dismiss' i], button:has-text('Done')")
                    if dismiss_btn:
                        dismiss_btn.click()
                        human_delay(1.0, 1.5)

                    result["status"] = "submitted"
                    result["details"] = "Successfully submitted application via LinkedIn Easy Apply."
                    return result

                # 6. Look for Review button
                review_btn = modal.query_selector(
                    "button[aria-label*='Review your application' i], button:has-text('Review')"
                )
                if review_btn:
                    logger.info("Navigating through Review step...")
                    review_btn.click()
                    human_delay(1.5, 2.5)
                    continue

                # 7. Look for Next button
                next_btn = modal.query_selector(
                    "button[aria-label*='Continue to next step' i], button:has-text('Next')"
                )
                if next_btn:
                    next_btn.click()
                    human_delay(1.5, 2.5)
                else:
                    # Form may have unhandled custom validation
                    result["status"] = "queued_manual"
                    result["details"] = f"Complex custom questions required manual completion at step {step + 1}."
                    break

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Navigation timeout on LinkedIn job page."
        except Exception as e:
            if "ERR_TOO_MANY_REDIRECTS" in str(e):
                logger.warning("LinkedIn session cookie caused redirect loop. Retrying with clean session...")
                try:
                    self.page.context.clear_cookies()
                    self.page.goto(target_url, timeout=20000, wait_until="domcontentloaded")
                    external_btn = self.page.query_selector(
                        "a.jobs-apply-button, a[aria-label*='Apply' i], a:has-text('Apply'), button:has-text('Apply')"
                    )
                    if external_btn:
                        href = external_btn.get_attribute("href")
                        if href and ("linkedin.com/safety/go" in href or "url=" in href):
                            parsed = urllib.parse.urlparse(href)
                            qs = urllib.parse.parse_qs(parsed.query)
                            if "url" in qs and qs["url"]:
                                href = urllib.parse.unquote(qs["url"][0])
                        return {
                            "status": "external_apply",
                            "external_url": href or target_url,
                            "details": "Redirected from public LinkedIn listing to external application portal.",
                        }
                except Exception as retry_err:
                    logger.debug("Clean session retry error: %s", retry_err)

            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during LinkedIn apply: %s", e)

        return result
