"""Discord Frontend & Notification Suite for AetherApply.
Serves as the primary operational UI/frontend:
- Real-time pipeline lifecycle events (Start, Finish)
- High-match job discovery cards with direct 1-click apply links
- Instant application submission receipts
- Error and issue tracking with actionable details
- GitHub Actions failure notifications
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("aetherapply.notifications.discord")


def _get_webhook_url(custom_url: Optional[str] = None) -> Optional[str]:
    if custom_url is not None:
        url = custom_url.strip()
    else:
        url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    return url if url else None


def _post_payload(payload: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    url = _get_webhook_url(webhook_url)
    if not url:
        return False
    try:
        resp = requests.post(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.error("Failed delivering Discord payload: %s", e)
        return False


def notify_pipeline_start(candidate: str, platforms: List[str], webhook_url: Optional[str] = None) -> bool:
    """Sends an alert when the 4-hour pipeline cycle begins."""
    payload = {
        "username": "AetherApply Engine",
        "avatar_url": "https://img.icons8.com/color/512/cloud-checked.png",
        "embeds": [
            {
                "title": "⚡ AetherApply Automation Started",
                "description": f"Starting automated 4-hour discovery & apply cycle for **{candidate}**.",
                "color": 0x3498DB,  # Blue
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": [
                    {
                        "name": "🌐 Active Platforms",
                        "value": ", ".join(platforms) if platforms else "None",
                        "inline": False,
                    }
                ],
                "footer": {"text": "AetherApply Cloud Runner • GitHub Actions"},
            }
        ],
    }
    return _post_payload(payload, webhook_url)


def notify_high_match_job(job: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """
    Sends an individual opportunity card whenever a high-matching job is found.
    Acts as a 1-click apply alert on Discord.
    """
    title = job.get("title", "Unknown Title")
    company = job.get("company", "Unknown Company")
    platform = job.get("platform", "Web")
    score = job.get("match_score", 0.0)
    url = job.get("url") or "https://linkedin.com"
    location = job.get("location") or "Remote / India"
    matched_skills = job.get("matched_skills", [])
    skills_str = ", ".join(matched_skills[:8]) if matched_skills else "Cloud / DevOps Stack"

    payload = {
        "username": "AetherApply Job Radar",
        "avatar_url": "https://img.icons8.com/color/512/starred-ticket.png",
        "embeds": [
            {
                "title": f"🎯 High Match Opportunity ({score}%): {title}",
                "description": f"**Company:** {company}\n**Platform:** {platform}\n**Location:** {location}\n\n**Matched Skills:** `{skills_str}`",
                "color": 0x2ECC71 if score >= 75 else 0xF39C12,  # Green / Gold
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": [
                    {
                        "name": "🔗 Application Link",
                        "value": f"[Click here to View & Apply on {platform}]({url})",
                        "inline": False,
                    }
                ],
                "footer": {"text": f"Status: {job.get('status', 'queued_apply')}"},
            }
        ],
    }
    return _post_payload(payload, webhook_url)


def notify_application_submitted(job: Dict[str, Any], details: str = "", webhook_url: Optional[str] = None) -> bool:
    """Sends a receipt whenever an application is automatically submitted."""
    title = job.get("title", "Unknown Role")
    company = job.get("company", "Company")
    platform = job.get("platform", "Platform")
    url = job.get("url") or "#"

    payload = {
        "username": "AetherApply Applier",
        "avatar_url": "https://img.icons8.com/color/512/checked-checkbox.png",
        "embeds": [
            {
                "title": f"✅ Application Successfully Submitted: {title}",
                "description": f"Applied to **{company}** on **{platform}**.\n\n**Details:** {details}",
                "color": 0x2ECC71,  # Green
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "AetherApply Automated Submission"},
            }
        ],
    }
    return _post_payload(payload, webhook_url)


def notify_issue(category: str, description: str, error_details: Optional[str] = None, webhook_url: Optional[str] = None) -> bool:
    """Sends an issue/alert to Discord (e.g. CAPTCHA, authentication failure, scraper error)."""
    fields = []
    if error_details:
        fields.append({
            "name": "Error Trace / Details",
            "value": f"```{error_details[:1000]}```",
            "inline": False,
        })

    payload = {
        "username": "AetherApply Alerts",
        "avatar_url": "https://img.icons8.com/color/512/warning-shield.png",
        "embeds": [
            {
                "title": f"⚠️ Issue Alert: {category}",
                "description": description,
                "color": 0xE74C3C,  # Red
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": fields,
                "footer": {"text": "AetherApply Self-Healing Monitor"},
            }
        ],
    }
    return _post_payload(payload, webhook_url)


def send_discord_alert(stats: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """Sends the end-of-run executive summary embed to Discord."""
    url = _get_webhook_url(webhook_url)
    if not url:
        return False

    errors = stats.get("errors", [])
    submitted = stats.get("applications_submitted", 0)
    manual_review = stats.get("manual_review_jobs", 0)
    high_match = stats.get("high_match_jobs", 0)
    new_jobs = stats.get("new_jobs_stored", 0)
    total_discovered = stats.get("total_discovered", 0)
    platforms = ", ".join(stats.get("platforms_scanned", [])) or "None"

    if errors:
        color = 0xE74C3C
        status_text = "⚠️ Completed with Issues"
    elif submitted > 0:
        color = 0x2ECC71
        status_text = "✅ Successful Applications Submitted"
    elif high_match > 0:
        color = 0x9B59B6  # Purple
        status_text = "🎯 High-Match Roles Ready"
    else:
        color = 0x3498DB
        status_text = "🔍 Cycle Completed"

    embed = {
        "title": f"📊 AetherApply 4h Report: {status_text}",
        "description": f"Automated cycle results for **{stats.get('candidate', 'Avinash')}**.",
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": [
            {"name": "🌐 Platforms", "value": platforms, "inline": False},
            {"name": "🔎 Discovered", "value": f"**{total_discovered}**", "inline": True},
            {"name": "💾 Saved to DB", "value": f"**{new_jobs}**", "inline": True},
            {"name": "🎯 High Match", "value": f"**{high_match}**", "inline": True},
            {"name": "📝 Applied", "value": f"**{submitted}**", "inline": True},
            {"name": "⚠️ Manual Queue", "value": f"**{manual_review}**", "inline": True},
        ],
        "footer": {"text": "Discord Frontend • AetherApply"},
    }

    if errors:
        err_text = "\n".join(f"• {e[:120]}" for e in errors[:3])
        embed["fields"].append({
            "name": "❌ Errors",
            "value": f"```{err_text}```",
            "inline": False,
        })

    payload = {
        "username": "AetherApply Frontend",
        "avatar_url": "https://img.icons8.com/color/512/cloud-checked.png",
        "embeds": [embed],
    }
    return _post_payload(payload, url)
