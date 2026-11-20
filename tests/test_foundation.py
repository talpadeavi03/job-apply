"""Unit tests for AetherApply Foundation (Sprint 1)."""
import os
import pytest
from database.db import get_session, init_db
from database.models import Job, ApplicationRecord, ProcessedMessage
from engine.dedup import generate_job_hash, normalize_text
from engine.parser import extract_resume_profile, ResumeProfile
from engine.matcher import JobMatcher
from config.settings import RESUME_PATH, load_platforms_config
from connectors.registry import get_active_connectors


def test_database_initialization():
    init_db()
    with get_session() as session:
        # Test inserting and querying a job
        test_hash = generate_job_hash("Cloud Engineer", "TestCorp", "LinkedIn", "https://linkedin.com/jobs/1")
        existing = session.query(Job).filter_by(job_hash=test_hash).first()
        if not existing:
            job = Job(
                job_hash=test_hash,
                title="Cloud Engineer",
                company="TestCorp",
                platform="LinkedIn",
                url="https://linkedin.com/jobs/1",
                match_score=85.0,
                status="queued_apply",
                source="test",
            )
            session.add(job)
            session.flush()

        retrieved = session.query(Job).filter_by(job_hash=test_hash).first()
        assert retrieved is not None
        assert retrieved.title == "Cloud Engineer"
        assert retrieved.match_score == 85.0


def test_dedup_hash_consistency():
    h1 = generate_job_hash("Senior DevOps Engineer", "Accenture", "LinkedIn", "https://example.com/job?ref=123")
    h2 = generate_job_hash("senior devops engineer", "Accenture", "linkedin", "https://example.com/job?track=abc")
    assert h1 == h2


def test_resume_parser():
    profile = extract_resume_profile(RESUME_PATH)
    assert profile.name == "Avinash Vishnu Talpade"
    assert "azure" in profile.skills
    assert "kubernetes" in profile.skills
    assert "terraform" in profile.skills
    assert len(profile.raw_text) > 0


def test_job_matcher():
    profile = extract_resume_profile(RESUME_PATH)
    matcher = JobMatcher(profile)

    # Strong match
    result = matcher.match(
        title="Azure Cloud & DevOps Engineer",
        description="Looking for an engineer skilled in Terraform, Kubernetes, Helm, Docker, and CI/CD pipelines."
    )
    assert result["score"] >= 70.0
    assert result["status"] == "queued_apply"
    assert "azure" in result["matched_skills"]
    assert "kubernetes" in result["matched_skills"]

    # Poor match
    poor_result = matcher.match(
        title="Senior Chef / Kitchen Assistant",
        description="Responsible for preparing italian cuisine and managing kitchen staff."
    )
    assert poor_result["score"] < 40.0
    assert poor_result["status"] == "rejected"


def test_platforms_config():
    conf = load_platforms_config()
    assert "platforms" in conf
    assert "gmail" in conf["platforms"]
    assert "linkedin" in conf["platforms"]
    assert "naukri" in conf["platforms"]
    assert "indeed" in conf["platforms"]
    assert "wellfound" in conf["platforms"]
    assert "hirist" in conf["platforms"]

    connectors = get_active_connectors(conf)
    connector_names = [c.name for c in connectors]
    assert "Indeed" in connector_names
    assert "Wellfound" in connector_names
    assert "Hirist" in connector_names


def test_discord_alert_graceful_fallback():
    from notifications.discord import send_discord_alert
    # Without webhook URL, should return False without raising exceptions
    res = send_discord_alert({"candidate": "Avinash", "total_discovered": 10}, webhook_url="")
    assert res is False


def test_mcp_tools():
    from mcp_server.server import (
        get_candidate_profile,
        get_resume_file_path,
        answer_application_question,
        evaluate_job_match,
        generate_custom_cover_letter
    )
    profile = get_candidate_profile()
    assert profile["name"] == "Avinash Vishnu Talpade"

    path = get_resume_file_path()
    assert "AT_26_AI.pdf" in path

    ans_exp = answer_application_question("How many years of experience do you have?")
    assert "3.5" in ans_exp

    cl = generate_custom_cover_letter("Cloud Engineer", "Google")
    assert "Avinash" in cl
    assert "Accenture" in cl

    match = evaluate_job_match("Cloud Engineer", "Azure Kubernetes Terraform")
    assert match["score"] >= 60.0


def test_canonicalize_job_url():
    from engine.dedup import canonicalize_job_url

    # LinkedIn comm tracking redirect
    raw_li = "https://www.linkedin.com/comm/jobs/view/4483471135/?trackingId=9mG1f2eR7p&refId=abc&otpToken=xyz"
    clean_li = canonicalize_job_url(raw_li)
    assert clean_li == "https://www.linkedin.com/jobs/view/4483471135/"

    # Regional in.linkedin.com comm URL
    raw_in = "https://in.linkedin.com/comm/jobs/view/4474809810/?trackingId=123"
    assert canonicalize_job_url(raw_in) == "https://www.linkedin.com/jobs/view/4474809810/"

    # Naukri tracking query stripping
    raw_naukri = "https://www.naukri.com/job-listings-cloud-engineer-12345?src=jobsearchDesk&xp=1"
    assert canonicalize_job_url(raw_naukri) == "https://www.naukri.com/job-listings-cloud-engineer-12345"


def test_answers_question_matching():
    from application.answers import get_answer_for_question

    assert get_answer_for_question("How many years of total experience do you have?") == "3.5"
    assert get_answer_for_question("Are you legally authorized to work in India?") == "Yes"
    assert get_answer_for_question("Will you now or in the future require visa sponsorship?") == "No"
    assert get_answer_for_question("What is your current notice period in days?") == "0"
    assert get_answer_for_question("What is your notice period?") == "Immediate joiner (0 days)"
    assert get_answer_for_question("What is your availability to join?") == "Immediate"
    assert get_answer_for_question("What is your expected CTC in INR?") == "750000"
    assert get_answer_for_question("What is your current CTC?") == "450000"


def test_wellfound_applier_initialization():
    from application.wellfound_applier import WellfoundApplier
    from config.settings import RESUME_PATH
    applier = WellfoundApplier(page=None, resume_path=RESUME_PATH)
    assert applier.resume_path.exists()
    assert "AT_26_AI.pdf" in str(applier.resume_path)


def test_round_robin_selection():
    from database.models import Job
    # Simulate candidates from multiple platforms
    candidates = [
        Job(job_hash="1", title="DevOps", company="A", platform="LinkedIn", match_score=100.0),
        Job(job_hash="2", title="DevOps", company="B", platform="LinkedIn", match_score=100.0),
        Job(job_hash="3", title="DevOps", company="C", platform="Wellfound", match_score=95.0),
        Job(job_hash="4", title="DevOps", company="D", platform="Naukri", match_score=90.0),
    ]

    platform_buckets = {}
    for j in candidates:
        p = (j.platform or "other").strip().lower()
        platform_buckets.setdefault(p, []).append(j)

    queued = []
    max_apps = 3
    while len(queued) < max_apps and any(platform_buckets.values()):
        for p, bucket in list(platform_buckets.items()):
            if bucket:
                queued.append(bucket.pop(0))
                if len(queued) >= max_apps:
                    break

    assert len(queued) == 3
    platforms = [j.platform for j in queued]
    # Verify diversity across platforms
    assert "LinkedIn" in platforms
    assert "Wellfound" in platforms
    assert "Naukri" in platforms


def test_naukri_canonicalize_url():
    from engine.dedup import canonicalize_job_url

    raw_jd = "https://www.naukri.com/jd/job-listings-cloud-ops-engineer-naukri-assist-12345?src=cja&xp=2"
    clean_jd = canonicalize_job_url(raw_jd)
    assert clean_jd == "https://www.naukri.com/job-listings-cloud-ops-engineer-naukri-assist-12345"

    raw_router = "https://www.naukri.com/jd?xp=1&src=cja"
    clean_router = canonicalize_job_url(raw_router)
    assert "https://www.naukri.com/jd?xp=1&src=cja" == clean_router


def test_naukri_applier_initialization():
    from application.naukri_applier import NaukriApplier
    from config.settings import RESUME_PATH

    applier = NaukriApplier(page=None, resume_path=RESUME_PATH)
    assert applier.resume_path.exists()
    assert "AT_26_AI.pdf" in str(applier.resume_path)


def test_gmail_html_job_extraction():
    import base64
    from connectors.gmail import extract_html_job_links

    html_content = """
    <html>
        <body>
            <a href="https://www.naukri.com/jd/job-listings-devops-engineer-12345?src=cja">DevOps Engineer</a>
            <a href="https://www.naukri.com/durl/nEZb">Apply Now</a>
            <a href="https://www.naukri.com/unsubscribe">Unsubscribe</a>
        </body>
    </html>
    """
    b64_data = base64.urlsafe_b64encode(html_content.encode("utf-8")).decode("utf-8").rstrip("=")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": b64_data}
            }
        ]
    }
    extracted = extract_html_job_links(payload)
    assert len(extracted) == 2
    assert extracted[0]["anchor_text"] == "DevOps Engineer"
    assert "job-listings-devops-engineer" in extracted[0]["url"]
    assert "durl" in extracted[1]["url"]


def test_mcp_gemini_answer_form_question():
    from mcp_server.ai_agent import answer_form_question

    # Numeric experience questions
    ans_num = answer_form_question("How many years of experience do you have with Kubernetes?", field_type="number")
    assert ans_num in ["3.5", "3"]

    # Notice period questions
    ans_notice = answer_form_question("What is your official notice period in days?", field_type="number")
    assert ans_notice == "0"

    # Open-ended recruiter question
    ans_essay = answer_form_question(
        "Why are you interested in this Cloud Engineer position?",
        field_type="textarea",
        job_title="Senior Cloud Engineer",
    )
    assert len(ans_essay) > 20
    assert any(term in ans_essay.lower() for term in ["accenture", "cloud", "devops", "azure", "aws"])
