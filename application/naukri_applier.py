"""Naukri 1-Click Apply, AI Questionnaire Automation, and Session Handling."""
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
from mcp_server.ai_agent import answer_form_question, generate_ai_answer

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

    def apply_to_job(self, job_url: str, job_title: Optional[str] = None) -> Dict[str, Any]:
        """
        Attempts automated 1-click apply on a Naukri job listing.
        Handles direct apply, sticky headers, login prompts, AI questionnaires, and external portal redirects.
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

            # Fallback scroll if not found
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

            # External apply link handling (Apply on company website)
            if "company website" in btn_text or "external" in btn_text or (href and href.startswith("http") and "naukri.com" not in href):
                target_href = href or job_url
                logger.info("Naukri job redirects to external company website: %s", target_href)
                return {
                    "status": "external_apply",
                    "external_url": target_href,
                    "details": "Redirecting to external company application portal.",
                }

            # Listen for new tab or popup that opens upon clicking Apply
            opened_pages = []
            ctx = self.page.context
            listener = lambda p: opened_pages.append(p)
            ctx.on("page", listener)

            # Click Apply button
            logger.info("Clicking Naukri Apply button: %s", btn_text)
            apply_btn.click(force=True)
            human_delay(2.5, 4.0)

            # Check if an external redirect or new page occurred
            if opened_pages:
                try:
                    p = opened_pages[-1]
                    p.wait_for_load_state("domcontentloaded", timeout=10000)
                    ext_url = p.url
                    if ext_url and "naukri.com" not in ext_url and not ext_url.startswith("about:"):
                        logger.info("Naukri apply opened external career portal: %s", ext_url)
                        return {
                            "status": "external_apply",
                            "external_url": ext_url,
                            "details": f"Job opened external company application portal: {ext_url}",
                        }
                except Exception as p_err:
                    logger.debug("Checking popup error: %s", p_err)

            if "naukri.com" not in self.page.url and not self.page.url.startswith("about:"):
                logger.info("Current page navigated to external portal: %s", self.page.url)
                return {
                    "status": "external_apply",
                    "external_url": self.page.url,
                    "details": f"Navigated to external company application portal: {self.page.url}",
                }

            # Check if login drawer/modal opened
            login_drawer = self.page.query_selector(".drawer-wrapper, .login-layer, #usernameField, input[placeholder*='Email' i]")
            if login_drawer and login_drawer.is_visible():
                logger.info("Login required on Naukri page. Authenticating...")
                logged_in = self._handle_in_page_login()
                if not logged_in:
                    return {
                        "status": "queued_manual",
                        "details": "Naukri account sign-in required to submit application.",
                    }
                human_delay(2.5, 3.5)
                # Re-click apply button after login
                apply_btn = self.page.query_selector("#apply-button, .apply-button, button:has-text('Apply')")
                if apply_btn and apply_btn.is_visible():
                    apply_btn.click(force=True)
                    human_delay(2.5, 3.5)

            # Check for Questionnaire Modal / Recruiter Chatbot
            modal = self.page.query_selector(".apply-message, .bot-overlay, .chatbot-container, .modal, div[role='dialog'], .drawer-wrapper")
            if modal:
                logger.info("Naukri recruiter questionnaire detected. Answering questions with Gemini MCP...")

                # 1. Answer text & number inputs and textareas
                inputs = modal.query_selector_all("input[type='text'], input[type='number'], textarea")
                for inp in inputs:
                    try:
                        if not inp.is_visible() or inp.input_value():
                            continue
                        tag_name = inp.evaluate("el => el.tagName").lower()
                        inp_type = "textarea" if tag_name == "textarea" else (inp.get_attribute("type") or "text")

                        # Determine question context
                        context_parts = [
                            inp.get_attribute("placeholder") or "",
                            inp.get_attribute("name") or "",
                            inp.get_attribute("aria-label") or "",
                        ]
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            lbl = modal.query_selector(f"label[for='{inp_id}']")
                            if lbl:
                                context_parts.append(lbl.inner_text())

                        # Check preceding paragraph or question title in chatbot
                        parent_text = inp.evaluate("""el => {
                            let p = el.parentElement;
                            for (let i = 0; i < 3 && p; i++) {
                                const q = p.querySelector('.bot-msg, .question-text, label, p');
                                if (q && q.innerText) return q.innerText;
                                p = p.parentElement;
                            }
                            return '';
                        }""")
                        if parent_text:
                            context_parts.append(parent_text)

                        prompt_str = " ".join(filter(None, context_parts)).strip()
                        if not prompt_str:
                            prompt_str = f"Question for {job_title or 'Cloud Engineer'}"

                        ans = answer_form_question(prompt_str, field_type=inp_type, job_title=job_title)
                        inp.fill(ans)
                        human_delay(0.2, 0.5)
                    except Exception as inp_err:
                        logger.debug("Questionnaire input error: %s", inp_err)

                # 2. Select radio buttons / option pills
                radio_options = modal.query_selector_all("button:has-text('Yes'), label:has-text('Yes'), .chip:has-text('Yes'), input[value*='Yes' i]")
                for r in radio_options:
                    try:
                        if r.is_visible():
                            r.click()
                            human_delay(0.2, 0.4)
                    except Exception:
                        pass

                # 3. Handle resume upload if requested
                upload_resume(self.page, self.resume_path, selector=".chatbot-container input[type='file'], div[role='dialog'] input[type='file']")

                # 4. Look for Save & Apply or Submit inside modal
                submit_btn = modal.query_selector(
                    "button:has-text('Save & Apply'), button:has-text('Submit'), button:has-text('Apply Now'), button:has-text('Save')"
                )
                if submit_btn:
                    submit_btn.click(force=True)
                    human_delay(2.5, 3.5)

            # Strict Verification: Check for real submission proof
            already_applied_btn = self.page.query_selector("button:has-text('Already Applied'), .already-applied, :text('Already Applied')")
            applied_btn = self.page.query_selector("button:has-text('Applied'), :text('Applied')")
            success_banner = self.page.query_selector(".apply-message, .success-message, :text('Successfully Applied')")
            page_text = self.page.content().lower()

            is_submitted = (
                already_applied_btn is not None
                or (applied_btn is not None and applied_btn.is_visible())
                or (success_banner is not None and any(w in success_banner.inner_text().lower() for w in ["applied", "submitted", "sent"]))
                or "successfully applied" in page_text
                or "application sent to recruiter" in page_text
                or "application submitted" in page_text
            )

            # Check if login drawer is still blocking
            login_layer = self.page.query_selector(".drawer-wrapper, .login-layer, #usernameField")
            if login_layer and login_layer.is_visible():
                result["status"] = "queued_manual"
                result["details"] = "Naukri account sign-in required to complete application."
            elif is_submitted:
                result["status"] = "submitted"
                result["details"] = "Successfully applied on Naukri."
            else:
                result["status"] = "queued_manual"
                result["details"] = "Application not fully confirmed on Naukri; queued for manual review."

        except PlaywrightTimeoutError:
            result["status"] = "failed"
            result["error"] = "Timeout loading Naukri job page."
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.warning("Error during Naukri apply: %s", e)

        return result
