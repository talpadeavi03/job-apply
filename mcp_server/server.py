"""AetherApply Model Context Protocol (MCP) Server.
Empowers Gemini and AI agents to autonomously manage job discovery,
intelligent question answering, tailored cover letters, and form filling
using a single master resume profile.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer

from application.answers import ANSWERS, get_answer_for_question
from application.apply import AutoApplier
from browser.manager import BrowserManager
from config.settings import RESUME_PATH
from database.db import get_session
from database.models import Job
from engine.matcher import JobMatcher
from engine.parser import extract_resume_profile
from mcp_server.ai_agent import generate_ai_answer, generate_cover_letter

logger = logging.getLogger("aetherapply.mcp.server")

# Initialize MCP Server
app = MCPServer("AetherApply-Agent-Hub")


# --- MCP RESOURCES ---

@app.resource("resume://master")
def get_master_resume_resource() -> str:
    """Returns the raw extracted text and summary of the master PDF resume."""
    profile = extract_resume_profile(RESUME_PATH)
    return json.dumps({
        "candidate": profile.to_dict(),
        "resume_text": profile.raw_text,
    }, indent=2)


# --- MCP TOOLS ---

@app.tool()
def get_candidate_profile() -> Dict[str, Any]:
    """
    Returns the structured master profile of the candidate (Avinash Vishnu Talpade),
    including core cloud/DevOps skills, contact details, years of experience, and links.
    """
    profile = extract_resume_profile(RESUME_PATH)
    return profile.to_dict()


@app.tool()
def get_resume_file_path() -> str:
    """
    Returns the absolute filesystem path of the master PDF resume (AT_26_AI.pdf)
    ready for file attachment or browser upload.
    """
    return str(RESUME_PATH.resolve())


@app.tool()
def answer_application_question(
    question: str,
    job_title: Optional[str] = None,
    job_description: Optional[str] = None,
) -> str:
    """
    Answers ANY job application question (e.g. years of experience in Kubernetes,
    notice period, visa sponsorship, or open-ended essays like 'Why should we hire you?'),
    strictly grounded in the master resume.
    """
    # 1. Check quick heuristic matches (years, notice period, location, phone)
    quick_ans = get_answer_for_question(question)
    if quick_ans is not None:
        return quick_ans

    # 2. Use AI reasoning with Gemini for open-ended or custom questions
    return generate_ai_answer(question, job_title=job_title, job_description=job_description)


@app.tool()
def fill_form_field(field_label: str, field_type: str = "text") -> str:
    """
    Determines the exact value to populate into an HTML/ATS application form field
    given its label, placeholder, or name.
    """
    ans = get_answer_for_question(field_label)
    if ans is not None:
        return ans
    return generate_ai_answer(field_label)


@app.tool()
def generate_custom_cover_letter(
    job_title: str,
    company: str,
    job_description: Optional[str] = None,
) -> str:
    """
    Generates a tailored, professional cover letter for a specific job title and company
    highlighting the candidate's Cloud/DevOps achievements at Accenture.
    """
    return generate_cover_letter(job_title, company, job_description)


@app.tool()
def evaluate_job_match(job_title: str, job_description: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates how well a job posting matches the candidate's master resume.
    Returns match score (0-100), matched skills, and recommended action (queued_apply, manual_review, rejected).
    """
    profile = extract_resume_profile(RESUME_PATH)
    matcher = JobMatcher(profile)
    return matcher.match(title=job_title, description=job_description or "")


@app.tool()
def list_saved_jobs(status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Lists discovered jobs from the local database / tracking registry,
    optionally filtered by status ('discovered', 'queued_apply', 'manual_review', 'applied').
    """
    with get_session() as session:
        query = session.query(Job)
        if status:
            query = query.filter(Job.status == status)
        jobs = query.order_by(Job.match_score.desc()).limit(limit).all()

        return [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "platform": j.platform,
                "location": j.location,
                "url": j.url,
                "match_score": j.match_score,
                "status": j.status,
            }
            for j in jobs
        ]


@app.tool()
def apply_to_queued_jobs(max_applications: int = 3) -> Dict[str, int]:
    """
    Triggers automated browser application for top queued jobs (using Playwright
    headless browser, resume attachment, and form filling).
    """
    with BrowserManager(headless=True) as bm:
        applier = AutoApplier(browser_manager=bm)
        return applier.process_queued_applications(max_applications=max_applications)


def main():
    """Runs the MCP server via stdio transport."""
    asyncio.run(app.run_stdio_async())


if __name__ == "__main__":
    main()
