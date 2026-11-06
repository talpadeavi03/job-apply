"""Central auto-apply orchestrator."""
import logging
import os
from typing import Dict, List, Optional
from browser.manager import BrowserManager
from config.settings import RESUME_PATH
from database.db import get_session
from database.firestore import save_job_to_firestore
from database.models import ApplicationRecord, Job
from application.linkedin_applier import LinkedInApplier
from application.naukri_applier import NaukriApplier
from application.wellfound_applier import WellfoundApplier
from application.universal_form_applier import UniversalFormApplier
from notifications.discord import notify_application_submitted

logger = logging.getLogger("aetherapply.application.apply")


class AutoApplier:
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager

    def process_queued_applications(self, max_applications: Optional[int] = None) -> Dict[str, int]:
        """
        Finds jobs marked as 'queued_apply' (or unapplied high-match) and executes automated application
        using balanced round-robin selection across active platforms.
        """
        if max_applications is None:
            max_applications = int(os.getenv("MAX_APPLY_PER_CYCLE", "15"))

        stats = {"submitted": 0, "queued_manual": 0, "failed": 0}

        with get_session() as session:
            # Query all eligible high-match jobs
            all_candidates = (
                session.query(Job)
                .filter(
                    (Job.status == "queued_apply") |
                    ((Job.status == "manual_review") & (Job.match_score >= 70.0))
                )
                .order_by(Job.match_score.desc())
                .all()
            )

            if not all_candidates:
                logger.info("No applications currently queued for auto-apply.")
                return stats

            # Round-robin selection across platforms to prevent single-platform starvation
            platform_buckets: Dict[str, List[Job]] = {}
            for j in all_candidates:
                p = (j.platform or "other").strip().lower()
                platform_buckets.setdefault(p, []).append(j)

            queued_jobs: List[Job] = []
            while len(queued_jobs) < max_applications and any(platform_buckets.values()):
                for p, bucket in list(platform_buckets.items()):
                    if bucket:
                        queued_jobs.append(bucket.pop(0))
                        if len(queued_jobs) >= max_applications:
                            break

            logger.info("Selected %d candidate jobs across platforms %s for auto-apply.",
                        len(queued_jobs), list(platform_buckets.keys()))

            if not self.browser_manager:
                logger.warning("BrowserManager not available. Skipping application submission.")
                return stats

            context = self.browser_manager.new_context()
            page = context.new_page()

            try:
                for idx, job in enumerate(queued_jobs, 1):
                    logger.info("[%d/%d] Processing apply for: %s @ %s (Score: %.1f, Platform: %s)",
                                idx, len(queued_jobs), job.title, job.company, job.match_score or 0.0, job.platform)
                    apply_result = {"status": "queued_manual", "details": "Platform auto-apply in progress"}

                    try:
                        p_lower = (job.platform or "").lower()
                        if p_lower == "wellfound" and job.url:
                            applier = WellfoundApplier(page, resume_path=RESUME_PATH)
                            apply_result = applier.apply_to_job(job.url)
                        elif p_lower == "naukri" and job.url:
                            applier = NaukriApplier(page, resume_path=RESUME_PATH)
                            apply_result = applier.apply_to_job(job.url, job_title=job.title)
                        elif p_lower == "linkedin" and job.url:
                            applier = LinkedInApplier(page, resume_path=RESUME_PATH)
                            apply_result = applier.apply_to_job(job.url, job_title=job.title)
                        elif job.url:
                            # Universal ATS & External Portal Applier
                            universal = UniversalFormApplier(page, resume_path=RESUME_PATH)
                            apply_result = universal.fill_and_apply(job.url, job_title=job.title)
                        else:
                            apply_result["status"] = "queued_manual"
                            apply_result["details"] = "No direct application URL available; queued for review."

                        # Follow-through for external company redirects
                        if apply_result.get("status") == "external_apply" and apply_result.get("external_url"):
                            logger.info("Following external portal link for %s: %s", job.company, apply_result["external_url"])
                            universal = UniversalFormApplier(page, resume_path=RESUME_PATH)
                            apply_result = universal.fill_and_apply(apply_result["external_url"], job_title=job.title)

                    except Exception as apply_err:
                        logger.warning("Unexpected error during job %s apply: %s", job.id, apply_err)
                        apply_result = {"status": "failed", "details": str(apply_err), "error": str(apply_err)}
                    finally:
                        try:
                            page.goto("about:blank")
                        except Exception:
                            pass

                    status = apply_result.get("status", "queued_manual")
                    details = apply_result.get("details", "")
                    error = apply_result.get("error")

                    # Record application audit
                    app_record = ApplicationRecord(
                        job_id=job.id,
                        platform=job.platform,
                        status=status,
                        submission_details=details,
                        error_message=error,
                    )
                    session.add(app_record)

                    # Update Job status in DB
                    job.status = "applied" if status == "submitted" else "manual_review"
                    session.flush()

                    # Update in Firestore
                    save_job_to_firestore({
                        "job_hash": job.job_hash,
                        "title": job.title,
                        "company": job.company,
                        "platform": job.platform,
                        "status": job.status,
                        "match_score": job.match_score,
                        "details": details,
                    })

                    if status == "submitted":
                        notify_application_submitted(
                            {"title": job.title, "company": job.company, "platform": job.platform, "url": job.url},
                            details=details,
                        )

                    stats[status] = stats.get(status, 0) + 1

            finally:
                try:
                    page.close()
                    context.close()
                except Exception:
                    pass

        return stats
