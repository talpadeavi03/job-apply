"""Gmail Alert Connector discovering jobs from alert emails via Gmail API."""
import base64
import logging
import os
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.settings import (
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN,
)
from connectors.base import BaseConnector
from database.db import get_session
from database.models import ProcessedMessage
from engine.dedup import canonicalize_job_url

logger = logging.getLogger("aetherapply.connectors.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

JOB_TERMS = re.compile(
    r"\b(job|jobs|career|careers|hiring|vacancy|vacancies|recruit|recruitment|opening|opportunity|apply now|job alert)\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

PLATFORM_PATTERNS = [
    ("LinkedIn", re.compile(r"linkedin\.com", re.IGNORECASE)),
    ("Naukri", re.compile(r"naukri\.com", re.IGNORECASE)),
    ("Indeed", re.compile(r"indeed\.com", re.IGNORECASE)),
    ("Foundit", re.compile(r"foundit\.in|monsterindia\.com", re.IGNORECASE)),
    ("Wellfound", re.compile(r"wellfound\.com|angel\.co", re.IGNORECASE)),
    ("Glassdoor", re.compile(r"glassdoor\.com", re.IGNORECASE)),
    ("Hirist", re.compile(r"hirist\.tech|hirist\.com", re.IGNORECASE)),
    ("AmbitionBox", re.compile(r"ambitionbox\.com", re.IGNORECASE)),
]


def _decode_data(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _walk_parts(payload: dict):
    if payload.get("body", {}).get("data"):
        yield payload.get("mimeType", ""), _decode_data(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        yield from _walk_parts(part)


def extract_body(payload: dict) -> str:
    parts = list(_walk_parts(payload))
    plain = [body for mime, body in parts if mime == "text/plain"]
    html = [body for mime, body in parts if mime == "text/html"]
    if plain:
        text = "\n".join(plain)
    elif html:
        text = BeautifulSoup("\n".join(html), "html.parser").get_text(" ", strip=True)
    else:
        text = ""
    return re.sub(r"\s+", " ", text).strip()[:20000]


def extract_html_job_links(payload: dict) -> List[Dict[str, str]]:
    """Extracts job listing links and their anchor titles directly from HTML payload."""
    parts = list(_walk_parts(payload))
    html_parts = [b for mime, b in parts if mime == "text/html"]
    if not html_parts:
        return []

    soup = BeautifulSoup("\n".join(html_parts), "html.parser")
    extracted: List[Dict[str, str]] = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href.startswith("http"):
            continue
        # Filter out common noise
        if any(term in href.lower() for term in ["unsubscribe", "mailto:", "facebook.com", "preferences", "settings", "feedback"]):
            continue

        is_job_url = any(term in href.lower() for term in [
            "/jobs/view/", "job-listings", "/jd?", "/durl/", "viewjob", "/careers/", "/job/"
        ])
        if not is_job_url or href in seen_urls:
            continue
        seen_urls.add(href)

        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        extracted.append({"url": href, "anchor_text": text})

    return extracted


class GmailConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any], browser_manager=None):
        super().__init__(config, browser_manager)
        self.service = None

    def authenticate(self) -> bool:
        """Authenticates using Gmail OAuth refresh token."""
        client_id = GMAIL_CLIENT_ID or os.getenv("GMAIL_CLIENT_ID")
        client_secret = GMAIL_CLIENT_SECRET or os.getenv("GMAIL_CLIENT_SECRET")
        refresh_token = GMAIL_REFRESH_TOKEN or os.getenv("GMAIL_REFRESH_TOKEN")

        if not (client_id and client_secret and refresh_token):
            logger.warning("Gmail credentials missing in environment. Gmail connector will be skipped.")
            return False

        try:
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            self.service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            logger.info("Successfully authenticated with Gmail API.")
            return True
        except Exception as e:
            logger.error("Gmail authentication failed: %s", e)
            return False

    def is_message_seen(self, message_id: str) -> bool:
        with get_session() as session:
            record = session.query(ProcessedMessage).filter_by(message_id=message_id).first()
            return record is not None

    def mark_message_seen(self, message_id: str) -> None:
        with get_session() as session:
            session.merge(ProcessedMessage(message_id=message_id, source="gmail"))

    def detect_platform(self, sender: str, subject: str, links: List[str]) -> str:
        combined = f"{sender} {subject} " + " ".join(links)
        for platform_name, pattern in PLATFORM_PATTERNS:
            if pattern.search(combined):
                return platform_name
        return "Gmail Alert"

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.service and not self.authenticate():
            return []

        query = self.config.get("query", "label:inbox is:unread (job OR career OR hiring)")
        max_emails = min(int(self.config.get("max_emails", 50)), 100)

        discovered: List[Dict[str, Any]] = []

        try:
            response = self.service.users().messages().list(userId="me", q=query, maxResults=max_emails).execute()
            message_refs = response.get("messages", [])
            logger.info("Gmail query '%s' returned %d message references.", query, len(message_refs))

            for ref in message_refs:
                msg_id = ref["id"]
                if self.is_message_seen(msg_id):
                    continue

                msg = self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                payload = msg.get("payload", {})
                headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
                subject = headers.get("subject", "Job Alert")
                sender = headers.get("from", "")
                snippet = msg.get("snippet", "")
                body_text = extract_body(payload)

                full_text = f"{subject} {snippet} {body_text}"
                if not JOB_TERMS.search(full_text):
                    self.mark_message_seen(msg_id)
                    continue

                # Extract HTML job links if present
                html_job_items = extract_html_job_links(payload)

                clean_title = re.sub(r"^(re:\s*|fwd:\s*|job alert:\s*)", "", subject, flags=re.IGNORECASE).strip()
                company_match = re.search(r"\bat\s+([A-Za-z0-9\s]+?)(?:\s+in|\s+for|\s+is|\s*[\-\|\:]|$)", clean_title, re.IGNORECASE)
                default_company = company_match.group(1).strip() if company_match else "Recruiter / Company"

                if html_job_items:
                    for item in html_job_items[:15]:
                        c_url = canonicalize_job_url(item["url"])
                        if not c_url:
                            continue
                        anchor = item.get("anchor_text", "").strip()
                        job_title = anchor if len(anchor) > 4 and not any(x in anchor.lower() for x in ["apply", "view all", "click", "read more"]) else clean_title
                        item_platform = self.detect_platform(sender, job_title, [c_url])

                        discovered.append({
                            "title": job_title[:200],
                            "company": default_company[:100],
                            "platform": item_platform,
                            "location": "Remote / India",
                            "url": c_url,
                            "description": full_text[:10000],
                            "source": "gmail_alert",
                            "source_id": f"{msg_id}_{hash(c_url)}",
                        })
                else:
                    links = list(dict.fromkeys(URL_RE.findall(body_text or snippet)))
                    filtered_links = [
                        u.rstrip(".,);]")
                        for u in links
                        if not any(x in u.lower() for x in ("unsubscribe", "mailto:", "facebook.com", "preferences", "settings"))
                    ]

                    platform = self.detect_platform(sender, subject, filtered_links)

                    # Prioritize links that point directly to job listings
                    job_links = [
                        u for u in filtered_links
                        if any(term in u.lower() for term in ["/jobs/view/", "viewjob", "job-listings", "/careers/", "/job/", "/jobs/", "apply"])
                    ]
                    raw_url = job_links[0] if job_links else (filtered_links[0] if filtered_links else None)
                    primary_url = canonicalize_job_url(raw_url) if raw_url else None

                    discovered.append({
                        "title": clean_title[:200],
                        "company": default_company[:100],
                        "platform": platform,
                        "location": "Remote / India",
                        "url": primary_url,
                        "description": full_text[:10000],
                        "source": "gmail_alert",
                        "source_id": msg_id,
                    })

                self.mark_message_seen(msg_id)

        except Exception as e:
            logger.error("Error during Gmail discovery: %s", e)

        return discovered

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        """Direct apply via Gmail alert links (to be followed by browser automation)."""
        logger.info("Queued job '%s' (%s) from Gmail for browser review/application.", job.get("title"), job.get("platform"))
        return False
