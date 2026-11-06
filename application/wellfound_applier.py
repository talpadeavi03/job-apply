"""Wellfound (formerly AngelList) automated application handler."""
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from application.answers import ANSWERS, get_answer_for_question
from application.uploader import upload_resume
from browser.utils import human_delay, safe_click, safe_fill
from config.settings import RESUME_PATH
from mcp_server.ai_agent import generate_ai_answer

logger = logging.getLogger("aetherapply.application.wellfound")


class WellfoundApplier:
    def __init__(self, page: Page, resume_path: Optional[Path] = None):
        self.page = page
        self.resume_path = resume_path or RESUME_PATH

    def apply_to_job(self, job_url: str) -> Dict[str, Any]:
        """
        Automates direct application on Wellfound job listings.
        Fills candidate details, answers screening questions, attaches master resume,
        and clicks Submit application.
        """
        result = {"status": "queued_manual", "details": "", "error": None}
        try:
            logger.info("Navigating to Wellfound job: %s", job_url)
            self.page.goto(job_url, timeout=30000, wait_until="domcontentloaded")
            human_delay(2.0, 3.0)

            # Check if already applied
            if self.page.query_selector("button:has-text('Applied'), :text('Applied')"):
                result["status"] = "submitted"
                result["details"] = "Already applied to this Wellfound position."
                return result

            # Find all potential apply buttons and select the visible one
            apply_btns = self.page.query_selector_all(
                "button:has-text('Apply Now'), a:has-text('Apply Now'), button:has-text('Apply')"
            )
            visible_apply_btn = next((b for b in apply_btns if b.is_visible()), None)

            if not visible_apply_btn:
                result["status"] = "queued_manual"
                result["details"] = "No visible Apply button found on Wellfound listing."
                return result

            # Click the visible Apply Now button
            logger.info("Clicking visible Wellfound Apply button...")
            visible_apply_btn.click()
            human_delay(2.0, 3.0)

            # Wait for modal dialog
            modal = self.page.query_selector("div[role='dialog'], .modal, [data-test='JobApplicationModal']")
            if not modal:
                result["status"] = "queued_manual"
                result["details"] = "Application modal did not open on Wellfound."
                return result

            # 1. Fill Name & Email
            name_inp = modal.query_selector("input[name='name'], input[placeholder*='Jane Doe' i]")
            if name_inp and not name_inp.input_value():
                name_inp.fill(ANSWERS["full_name"])

            email_inp = modal.query_selector("input[name='email'], input[type='email']")
            if email_inp and not email_inp.input_value():
                email_inp.fill(ANSWERS["email"])

            # 2. Fill Password if creating/linking candidate account
            pwd_inp = modal.query_selector("input[name='password']")
            if pwd_inp:
                pwd_inp.fill("CloudDevOps@2026!")
            pwd_conf = modal.query_selector("input[name='passwordConfirmation']")
            if pwd_conf:
                pwd_conf.fill("CloudDevOps@2026!")

            # 3. Fill Location / City
            loc_inp = modal.query_selector("input[placeholder*='San Francisco' i], input[name='location']")
            if loc_inp and not loc_inp.input_value():
                loc_inp.fill("Pune, India")

            # 4. Fill Desired Salary / Compensation
            sal_inp = modal.query_selector("input[name='desiredSalary'], input[type='number']")
            if sal_inp and not sal_inp.input_value():
                sal_inp.fill("18000")

            # 5. Radio Buttons: Work Authorization & Visa Sponsorship
            logger.info("Setting Wellfound authorization and sponsorship...")
            spons_no = modal.query_selector("input[name='requireSponsorship'][value='false'], input[name='requireSponsorship']")
            if spons_no:
                try:
                    spons_no.click(force=True)
                except Exception:
                    pass

            auth_yes = modal.query_selector("input[name='usAuthorized'][value='true'], input[name='usAuthorized']")
            if auth_yes:
                try:
                    auth_yes.click(force=True)
                except Exception:
                    pass

            # 6. Upload Master Resume
            logger.info("Uploading master resume to Wellfound...")
            uploaded = upload_resume(self.page, self.resume_path, selector="div[role='dialog'] input[type='file'], .modal input[type='file']")
            if uploaded:
                logger.info("Successfully attached master resume to Wellfound application.")

            # 7. Answer Recruiter Custom Essay / Question Textareas
            logger.info("Checking custom recruiter questions...")
            textareas = modal.query_selector_all("textarea")
            for ta in textareas:
                try:
                    if not ta.is_visible() or ta.input_value():
                        continue
                    context = (ta.get_attribute("name") or "") + " " + (ta.get_attribute("placeholder") or "")
                    lbl = modal.query_selector(f"label[for='{ta.get_attribute('id')}']")
                    if lbl:
                        context += " " + lbl.inner_text()

                    ai_ans = generate_ai_answer(question=context if len(context) > 5 else "Why are you interested in this role?")
                    ta.fill(ai_ans)
                    human_delay(0.3, 0.6)
                except Exception as ta_err:
                    logger.debug("Wellfound textarea error: %s", ta_err)

            # 8. Submit Application
            logger.info("Looking for submit button on Wellfound modal...")
            submit_btns = modal.query_selector_all(
                "button[type='submit'], button:has-text('Submit application'), button:has-text('Send Application')"
            )
            visible_submit = next((b for b in submit_btns if b.is_visible()), None)

            if visible_submit:
                logger.info("Found submit button on Wellfound form. Submitting application...")
                human_delay(1.0, 2.0)
                visible_submit.click(force=True)
                human_delay(3.0, 5.0)

                result["status"] = "submitted"
                result["details"] = "Successfully auto-applied to role via Wellfound."
                return result
            else:
                result["status"] = "queued_manual"
                result["details"] = "Wellfound form pre-populated; submission button not ready."

        except PlaywrightTimeoutError as te:
            result["status"] = "failed"
            result["error"] = f"Timeout during Wellfound apply: {te}"
            logger.warning("Timeout during Wellfound apply: %s", te)
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during Wellfound apply: %s", e)

        return result
