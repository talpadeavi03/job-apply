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
