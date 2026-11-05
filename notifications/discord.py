"""Discord Webhook notification service for AetherApply pipeline results."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from config.settings import ROOT_DIR

logger = logging.getLogger("aetherapply.notifications.discord")


def send_discord_alert(stats: Dict[str, Any], webhook_url: Optional[str] = None) -> bool:
    """
    Sends a rich formatted embed report to a Discord channel via Webhook.
    """
    if webhook_url is not None:
        url = webhook_url.strip()
    else:
        url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    if not url:
        logger.debug("DISCORD_WEBHOOK_URL not configured. Skipping Discord alert.")
        return False

    errors = stats.get("errors", [])
    submitted = stats.get("applications_submitted", 0)
    manual_review = stats.get("manual_review_jobs", 0)
    high_match = stats.get("high_match_jobs", 0)
    new_jobs = stats.get("new_jobs_stored", 0)
    total_discovered = stats.get("total_discovered", 0)
    platforms = ", ".join(stats.get("platforms_scanned", [])) or "None"

    # Determine status color
    # Green (0x2ECC71) if submitted, Red (0xE74C3C) if errors, Orange (0xF39C12) if manual review, Blue (0x3498DB) default
    if errors:
        color = 0xE74C3C
        status_text = "⚠️ Completed with Errors"
    elif submitted > 0:
        color = 0x2ECC71
        status_text = "✅ Successful Applications Submitted"
    elif manual_review > 0:
        color = 0xF39C12
        status_text = "📋 Opportunities Found — Needs Review"
    else:
        color = 0x3498DB
        status_text = "🔍 Pipeline Cycle Completed"

    embed = {
        "title": f"🚀 AetherApply Status: {status_text}",
        "description": f"Automated 4-hour job discovery and application run summary for **{stats.get('candidate', 'Avinash')}**.",
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": [
            {
                "name": "🌐 Platforms Scanned",
                "value": platforms,
                "inline": False,
            },
            {
                "name": "🔎 Discovered",
                "value": f"**{total_discovered}** opportunities",
                "inline": True,
            },
            {
                "name": "💾 New Saved in DB",
                "value": f"**{new_jobs}** jobs",
                "inline": True,
            },
            {
                "name": "🎯 High Match (Queued)",
                "value": f"**{high_match}** jobs",
                "inline": True,
            },
            {
                "name": "📝 Applications Submitted",
                "value": f"**{submitted}** applied",
                "inline": True,
            },
            {
                "name": "⚠️ Manual Review Queue",
                "value": f"**{manual_review}** jobs",
                "inline": True,
            },
        ],
        "footer": {
            "text": "AetherApply Cloud Runner • GitHub Actions + Firebase",
        },
    }

    # Add error details if any occurred
    if errors:
        error_lines = "\n".join(f"• {e[:120]}" for e in errors[:3])
        embed["fields"].append({
            "name": "❌ Errors Encountered",
            "value": f"```{error_lines}```",
            "inline": False,
        })

    payload = {
        "username": "AetherApply Bot",
        "avatar_url": "https://img.icons8.com/color/512/cloud-checked.png",
        "embeds": [embed],
    }

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code in (200, 204):
            logger.info("Successfully delivered Discord webhook notification.")
            return True
        else:
            logger.warning("Discord webhook returned status %d: %s", response.status_code, response.text)
            return False
    except Exception as e:
        logger.error("Failed to send Discord webhook: %s", e)
        return False
