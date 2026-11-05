"""Deduplication and unique identity hashing for job postings."""
import hashlib
import re
from typing import Optional


def normalize_text(text: Optional[str]) -> str:
    """Normalizes text by lowercasing, stripping punctuation and redundant whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_job_url(url: Optional[str]) -> Optional[str]:
    """
    Strips email tracking redirects, tokens, and normalizes URLs to canonical job landing pages.
    Specifically handles LinkedIn comm tracking links, Naukri, and Indeed links.
    """
    if not url:
        return None
    url = url.strip()

    # 1. Normalize LinkedIn tracking / email comm URLs
    li_match = re.search(r"linkedin\.com/(?:[a-z]{2}/)?(?:comm/)?jobs/view/.*?(\d{8,12})", url, re.IGNORECASE)
    if not li_match:
        li_match = re.search(r"linkedin\.com/(?:[a-z]{2}/)?(?:comm/)?jobs/view/(\d+)", url, re.IGNORECASE)
    if li_match:
        job_id = li_match.group(1)
        return f"https://www.linkedin.com/jobs/view/{job_id}/"

    # 2. Normalize Naukri URLs (strip tracking query params)
    if "naukri.com" in url:
        return url.split("?")[0].rstrip("/")

    # 3. Normalize Indeed URLs
    ind_match = re.search(r"indeed\.com/.*?[?&]jk=([a-f0-9]+)", url, re.IGNORECASE)
    if ind_match:
        return f"https://www.indeed.com/viewjob?jk={ind_match.group(1)}"

    # Default: strip common tracking queries
    return url.split("?")[0].rstrip("/") if "?" in url else url.rstrip("/")


def generate_job_hash(title: str, company: str, platform: str, url: Optional[str] = None) -> str:
    """
    Generates a deterministic 64-character SHA-256 hash representing a unique job opportunity.
    Clean URL query params to avoid duplicate tracking parameters.
    """
    norm_title = normalize_text(title)
    norm_company = normalize_text(company)
    norm_platform = normalize_text(platform)

    clean_url = ""
    if url:
        canonical = canonicalize_job_url(url)
        clean_url = canonical.lower() if canonical else ""

    identity = f"{norm_platform}|{norm_company}|{norm_title}|{clean_url}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
