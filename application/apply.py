"""Central auto-apply orchestrator."""
import logging
from typing import Dict, List, Optional
from browser.manager import BrowserManager
from config.settings import RESUME_PATH
from database.db import get_session
from database.firestore import save_job_to_firestore
from database.models import ApplicationRecord, Job
from application.linkedin_applier import LinkedInApplier
from notifications.discord import notify_application_submitted

logger = logging.getLogger("aetherapply.application.apply")


class AutoApplier:
    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager

    def process_queued_applications(self, max_applications: int = 5) -> Dict[str, int]:
        """
        Finds jobs marked as 'queued_apply' and attempts automated application.
        """
        stats = {"submitted": 0, "queued_manual": 0, "failed": 0}

        with get_session() as session:
            queued_jobs = (
                session.query(Job)
                .filter(Job.status == "queued_apply")
                .order_by(Job.match_score.desc())
                .limit(max_applications)
                .all()
            )

            if not queued_jobs:
                logger.info("No applications currently queued for auto-apply.")
                return stats

            logger.info("Found %d queued jobs for auto-apply.", len(queued_jobs))

            if not self.browser_manager:
                logger.warning("BrowserManager not available. Skipping application submission.")
                return stats

            context = self.browser_manager.new_context()
            page = context.new_page()

            try:
                for job in queued_jobs:
                    logger.info("Processing apply for: %s @ %s (%s)", job.title, job.company, job.platform)
                    apply_result = {"status": "queued_manual", "details": "Platform auto-apply in progress"}

                    if job.platform.lower() == "linkedin" and job.url:
                        applier = LinkedInApplier(page, resume_path=RESUME_PATH)
                        apply_result = applier.apply_to_job(job.url)
                    else:
                        apply_result["status"] = "queued_manual"
                        apply_result["details"] = f"Automated apply not yet enabled for {job.platform}; queued for review."

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
                    })

                    if status == "submitted":
                        notify_application_submitted(
                            {"title": job.title, "company": job.company, "platform": job.platform, "url": job.url},
                            details=details,
                        )

                    stats[status] = stats.get(status, 0) + 1

            finally:
                page.close()
                context.close()

        return stats
