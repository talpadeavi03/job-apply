"""Universal Form & ATS Applier (Greenhouse, Lever, Ashby, Workday, Indeed, External).
Automatically populates candidate details, attaches master resume,
and answers custom questions using the MCP / AI reasoning layer.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import ANSWERS, get_answer_for_question
from application.uploader import upload_resume
from browser.utils import human_delay, safe_click, safe_fill
from config.settings import RESUME_PATH
from mcp_server.ai_agent import answer_form_question, generate_ai_answer

logger = logging.getLogger("aetherapply.application.universal")


class UniversalFormApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def fill_and_apply(self, url: str, job_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Navigates to an application link (external ATS, career portal, or direct apply page),
        identifies form fields, uploads resume, answers custom prompts using Gemini MCP, and attempts submission.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            logger.info("Opening application URL: %s", url)
            self.page.goto(url, timeout=35000, wait_until="domcontentloaded")
            human_delay(2.5, 4.0)

            # Check if this portal requires an account / sign-in (e.g. Workday, Taleo, SuccessFactors)
            auth_wall = self.page.query_selector(
                "input[type='password'], button:has-text('Sign In'), a:has-text('Sign In'), button:has-text('Create Account')"
            )
            is_workday = any(x in self.page.url.lower() for x in ["myworkdayjobs.com", "workdayjobs.com", "taleo.net"])
            if auth_wall and is_workday:
                logger.info("External portal requires enterprise account sign-in (%s). Queuing for manual completion.", self.page.url)
                return {
                    "status": "queued_manual",
                    "details": f"Enterprise career portal requires candidate account registration/sign-in: {self.page.url}",
                }

            # If there is an "Apply Now" or "Apply" button leading to the form, click it
            apply_entry_btn = self.page.query_selector(
                "a:has-text('Apply Now'), button:has-text('Apply Now'), a:has-text('Apply for this job'), button:has-text('Apply')"
            )
            if apply_entry_btn and not self.page.query_selector("input[type='file'], input[name*='name' i]"):
                logger.info("Clicking initial Apply button to open form...")
                apply_entry_btn.click()
                human_delay(2.5, 4.0)

            # 1. Attach Master Resume PDF
            uploaded = upload_resume(self.page, self.resume_path, selector="input[type='file']")
            if uploaded:
                logger.info("Attached master resume AT_26_AI.pdf to application form.")

            # 2. Identify & Fill Standard Text / Email / Phone inputs
            inputs = self.page.query_selector_all("input[type='text'], input[type='email'], input[type='tel'], input[type='number'], input:not([type])")
            for inp in inputs:
                try:
                    if not inp.is_visible():
                        continue
                    current_val = inp.input_value()
                    if current_val:
                        continue  # Already pre-filled

                    context_str = " ".join(filter(None, [
                        inp.get_attribute("name") or "",
                        inp.get_attribute("id") or "",
                        inp.get_attribute("placeholder") or "",
                        inp.get_attribute("aria-label") or "",
                    ])).lower()

                    inp_id = inp.get_attribute("id")
                    if inp_id:
                        lbl = self.page.query_selector(f"label[for='{inp_id}']")
                        if lbl:
                            context_str += " " + lbl.inner_text().lower()

                    inp_type = inp.get_attribute("type") or "text"
                    answer = answer_form_question(context_str, field_type=inp_type, job_title=job_title)
                    if answer:
                        inp.fill(answer)
                        human_delay(0.2, 0.4)
                except Exception as e:
                    logger.debug("Field fill error: %s", e)

            # 3. Handle Textarea / Essay Questions using Gemini MCP Reasoning
            textareas = self.page.query_selector_all("textarea")
            for ta in textareas:
                try:
                    if not ta.is_visible() or ta.input_value():
                        continue
                    context = (ta.get_attribute("name") or "") + " " + (ta.get_attribute("placeholder") or "")
                    lbl = self.page.query_selector(f"label[for='{ta.get_attribute('id')}']")
                    if lbl:
                        context += " " + lbl.inner_text()

                    ai_ans = answer_form_question(context.strip() or f"Why are you a fit for the {job_title or 'Cloud Engineer'} role?", field_type="textarea", job_title=job_title)
                    ta.fill(ai_ans)
                    human_delay(0.4, 0.8)
                except Exception as ta_err:
                    logger.debug("Textarea error: %s", ta_err)

            # 4. Check for Submit button
            submit_btn = self.page.query_selector(
                "button[type='submit'], input[type='submit'], button:has-text('Submit Application'), "
                "button:has-text('Submit'), button:has-text('Apply Now'), button:has-text('Send Application')"
            )

            if submit_btn and (uploaded or len(inputs) > 0):
                logger.info("Found submit button on completed form. Submitting application...")
                human_delay(1.0, 2.0)
                submit_btn.click()
                human_delay(3.5, 5.0)

                # Strict Verification of submission
                page_text = self.page.content().lower()
                is_confirmed = any(term in page_text for term in [
                    "thank you for applying", "application submitted", "successfully applied",
                    "application received", "we have received your application"
                ]) or any(term in self.page.url.lower() for term in ["confirmation", "thanks", "submitted", "success"])

                if is_confirmed:
                    result["status"] = "submitted"
                    result["details"] = "Successfully auto-filled and submitted application form via Gemini MCP."
                else:
                    result["status"] = "queued_manual"
                    result["details"] = "Form auto-populated with master resume and Gemini answers; queued for final manual confirmation."
            else:
                result["status"] = "queued_manual"
                result["details"] = "Form auto-populated with master resume; queued for manual review."

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Page timeout while navigating to application form."
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during universal form apply: %s", e)

        return result
