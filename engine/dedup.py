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
        clean_url = url.split("?")[0].strip().lower()

    identity = f"{norm_platform}|{norm_company}|{norm_title}|{clean_url}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
