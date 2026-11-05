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
from mcp_server.ai_agent import generate_ai_answer

logger = logging.getLogger("aetherapply.application.universal")


class UniversalFormApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def fill_and_apply(self, url: str) -> Dict[str, Any]:
        """
        Navigates to an application link (external ATS, career portal, or direct apply page),
        identifies form fields, uploads resume, answers custom prompts, and attempts submission.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            logger.info("Opening application URL: %s", url)
            self.page.goto(url, timeout=35000, wait_until="domcontentloaded")
            human_delay(2.5, 4.0)

            # If there is an "Apply Now" or "Apply" button leading to the form, click it
            apply_entry_btn = self.page.query_selector(
                "a:has-text('Apply Now'), button:has-text('Apply Now'), a:has-text('Apply for this job'), button:has-text('Apply')"
            )
            if apply_entry_btn and not self.page.query_selector("input[type='file'], input[name*='name' i]"):
                logger.info("Clicking initial Apply button to open form...")
                apply_entry_btn.click()
                human_delay(2.0, 3.5)

            # 1. Attach Master Resume PDF
            uploaded = upload_resume(self.page, self.resume_path, selector="input[type='file']")
            if uploaded:
                logger.info("Attached master resume AT_26_AI.pdf to application form.")

            # 2. Identify & Fill Standard Text / Email / Phone inputs
            inputs = self.page.query_selector_all("input[type='text'], input[type='email'], input[type='tel'], input:not([type])")
            for inp in inputs:
                try:
                    if not inp.is_visible():
                        continue
                    current_val = inp.input_value()
                    if current_val:
                        continue  # Already pre-filled

                    # Extract context from placeholder, id, name, or preceding label
                    context_str = " ".join(filter(None, [
                        inp.get_attribute("name") or "",
                        inp.get_attribute("id") or "",
                        inp.get_attribute("placeholder") or "",
                        inp.get_attribute("aria-label") or "",
                    ])).lower()

                    # Find matching label text if present
                    inp_id = inp.get_attribute("id")
                    if inp_id:
                        lbl = self.page.query_selector(f"label[for='{inp_id}']")
                        if lbl:
                            context_str += " " + lbl.inner_text().lower()

                    # Answer inference
                    answer = None
                    if any(k in context_str for k in ["first_name", "firstname", "first name"]):
                        answer = ANSWERS["first_name"]
                    elif any(k in context_str for k in ["last_name", "lastname", "last name"]):
                        answer = ANSWERS["last_name"]
                    elif any(k in context_str for k in ["full_name", "fullname", "name"]):
                        answer = ANSWERS["full_name"]
                    elif any(k in context_str for k in ["email", "e-mail"]):
                        answer = ANSWERS["email"]
                    elif any(k in context_str for k in ["phone", "mobile", "contact", "tel"]):
                        answer = ANSWERS["phone"]
                    elif any(k in context_str for k in ["linkedin"]):
                        answer = ANSWERS["linkedin_url"]
                    elif any(k in context_str for k in ["website", "portfolio", "github"]):
                        answer = ANSWERS["portfolio_url"]
                    elif any(k in context_str for k in ["location", "city", "address"]):
                        answer = ANSWERS["location"]
                    else:
                        answer = get_answer_for_question(context_str)

                    if answer:
                        inp.fill(answer)
                        human_delay(0.2, 0.5)
                except Exception as e:
                    logger.debug("Field fill error: %s", e)

            # 3. Handle Textarea / Essay Questions using AI Reasoning
            textareas = self.page.query_selector_all("textarea")
            for ta in textareas:
                try:
                    if not ta.is_visible() or ta.input_value():
                        continue
                    context = (ta.get_attribute("name") or "") + " " + (ta.get_attribute("placeholder") or "")
                    lbl = self.page.query_selector(f"label[for='{ta.get_attribute('id')}']")
                    if lbl:
                        context += " " + lbl.inner_text()

                    # Generate grounded AI response
                    ai_ans = generate_ai_answer(question=context if len(context) > 5 else "Why are you interested in this role?")
                    ta.fill(ai_ans)
                    human_delay(0.4, 0.8)
                except Exception as ta_err:
                    logger.debug("Textarea error: %s", ta_err)

            # 4. Check for Submit or Review button
            submit_btn = self.page.query_selector(
                "button[type='submit'], input[type='submit'], button:has-text('Submit Application'), button:has-text('Submit')"
            )

            if submit_btn and uploaded:
                logger.info("Found submit button on completed form. Submitting application...")
                human_delay(1.0, 2.0)
                submit_btn.click()
                human_delay(3.0, 4.5)
                result["status"] = "submitted"
                result["details"] = "Successfully auto-filled and submitted application form."
            else:
                result["status"] = "queued_manual"
                result["details"] = "Form auto-populated with master resume; queued for final review."

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Page timeout while navigating to application form."
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during universal form apply: %s", e)

        return result
