"""AetherApply Orchestrator: Central 4-hour execution engine."""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from application.apply import AutoApplier
from browser.manager import BrowserManager
from config.settings import (
    CANDIDATE_NAME,
    DATA_DIR,
    LOGS_DIR,
    RESUME_PATH,
    load_platforms_config,
)
from connectors.registry import get_active_connectors
from database.db import get_session, init_db
from database.firestore import get_firestore_client, save_job_to_firestore
from database.models import Job
from engine.dedup import generate_job_hash
from engine.matcher import JobMatcher
from engine.parser import extract_resume_profile
from notifications.discord import (
    notify_batch_high_match_jobs,
    notify_high_match_job,
    notify_issue,
    notify_pipeline_start,
    send_discord_alert,
)

# Setup Logging
log_file = LOGS_DIR / "aetherapply.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ],
)
logger = logging.getLogger("aetherapply.main")


def run_pipeline() -> Dict[str, Any]:
    run_timestamp = datetime.now(timezone.utc).isoformat()
    logger.info("==========================================")
    logger.info("Starting AetherApply Workflow [%s]", run_timestamp)
    logger.info("==========================================")

    # 1. Initialize Database
    init_db()

    # 2. Load Configuration & Resume Profile
    platforms_config = load_platforms_config()
    resume_profile = extract_resume_profile(RESUME_PATH)
    logger.info(
        "Loaded master profile for %s with %d target skills.",
        resume_profile.name,
        len(resume_profile.skills),
    )

    matcher = JobMatcher(resume_profile)

    stats = {
        "run_at_utc": run_timestamp,
        "candidate": resume_profile.name,
        "platforms_scanned": [],
        "total_discovered": 0,
        "new_jobs_stored": 0,
        "high_match_jobs": 0,
        "manual_review_jobs": 0,
        "errors": [],
    }

    # 3. Launch single BrowserManager session
    high_match_alerts = []
    with BrowserManager(headless=True) as browser_mgr:
        active_connectors = get_active_connectors(platforms_config, browser_manager=browser_mgr)
        logger.info("Executing %d active connectors...", len(active_connectors))
        notify_pipeline_start(candidate=resume_profile.name, platforms=[c.name for c in active_connectors])

        for connector in active_connectors:
            platform_name = connector.name
            stats["platforms_scanned"].append(platform_name)
            logger.info("--> Scanning platform: %s", platform_name)

            try:
                discovered_jobs = connector.discover_jobs()
                stats["total_discovered"] += len(discovered_jobs)
                logger.info("Retrieved %d opportunities from %s", len(discovered_jobs), platform_name)

                # Process & Deduplicate Jobs
                with get_session() as session:
                    seen_hashes = set()
                    for item in discovered_jobs:
                        title = item.get("title", "Unknown Title")
                        company = item.get("company", "Unknown Company")
                        platform = item.get("platform", platform_name)
                        url = item.get("url")
                        description = item.get("description", "")
                        source = item.get("source", "connector")
                        source_id = item.get("source_id")

                        job_hash = generate_job_hash(title, company, platform, url)

                        # Skip duplicates within same batch or already in DB
                        if job_hash in seen_hashes:
                            continue
                        seen_hashes.add(job_hash)

                        existing = session.query(Job).filter_by(job_hash=job_hash).first()
                        if existing:
                            continue

                        # Evaluate Match Compatibility
                        match_result = matcher.match(title=title, description=description)
                        score = match_result["score"]
                        status = match_result["status"]

                        if status == "queued_apply":
                            stats["high_match_jobs"] += 1
                            high_match_alerts.append({
                                "title": title,
                                "company": company,
                                "platform": platform,
                                "location": item.get("location"),
                                "url": url,
                                "match_score": score,
                                "status": status,
                                "matched_skills": match_result.get("matched_skills", []),
                            })
                        elif status == "manual_review":
                            stats["manual_review_jobs"] += 1

                        new_job = Job(
                            job_hash=job_hash,
                            title=title,
                            company=company,
                            platform=platform,
                            location=item.get("location"),
                            url=url,
                            description=description[:15000] if description else None,
                            match_score=score,
                            status=status,
                            source=source,
                            source_id=source_id,
                        )
                        session.add(new_job)
                        stats["new_jobs_stored"] += 1

                        # Synchronize with Firebase Firestore (if enabled)
                        save_job_to_firestore({
                            "job_hash": job_hash,
                            "title": title,
                            "company": company,
                            "platform": platform,
                            "location": item.get("location"),
                            "url": url,
                            "description": description,
                            "match_score": score,
                            "status": status,
                            "source": source,
                            "source_id": source_id,
                        })

            except Exception as e:
                err_msg = f"Failed scanning {platform_name}: {str(e)}"
                logger.error(err_msg)
                stats["errors"].append(err_msg)
                notify_issue(
                    category=f"Platform Error ({platform_name})",
                    description=f"Automated scraper encountered an issue while querying {platform_name}.",
                    error_details=str(e),
                )

        # 4. Notify high-match jobs on Discord (top 5 cards + digest)
        if high_match_alerts:
            notify_batch_high_match_jobs(high_match_alerts)

        # 5. Auto-Apply to Queued High-Match Jobs
        logger.info("Starting automated application processing...")
        applier = AutoApplier(browser_manager=browser_mgr)
        apply_stats = applier.process_queued_applications(max_applications=5)
        stats["applications_submitted"] = apply_stats.get("submitted", 0)
        stats["applications_queued_manual"] = apply_stats.get("queued_manual", 0)

    # 4. Summary Output
    logger.info("==========================================")
    logger.info("AetherApply Pipeline Completed.")
    logger.info("New Jobs Stored: %d", stats["new_jobs_stored"])
    logger.info("High Match (Queued): %d", stats["high_match_jobs"])
    logger.info("Manual Review: %d", stats["manual_review_jobs"])
    logger.info("==========================================")

    # Append to GitHub Step Summary if running in GitHub Actions
    gh_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if gh_summary:
        try:
            with open(gh_summary, "a", encoding="utf-8") as f:
                f.write(f"### AetherApply Run Summary ({run_timestamp})\n")
                f.write(f"- **Candidate:** {stats['candidate']}\n")
                f.write(f"- **Platforms Scanned:** {', '.join(stats['platforms_scanned'])}\n")
                f.write(f"- **Total Opportunities Discovered:** {stats['total_discovered']}\n")
                f.write(f"- **New Jobs Stored in DB:** {stats['new_jobs_stored']}\n")
                f.write(f"- **High Match (Queued for Apply):** {stats['high_match_jobs']}\n")
                f.write(f"- **Manual Review:** {stats['manual_review_jobs']}\n")
                if stats["errors"]:
                    f.write(f"- **Errors:** {len(stats['errors'])}\n")
        except Exception as e:
            logger.warning("Could not write to GITHUB_STEP_SUMMARY: %s", e)

    # 5. Send Discord Notification (if configured)
    send_discord_alert(stats)

    return stats


def main():
    summary = run_pipeline()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
