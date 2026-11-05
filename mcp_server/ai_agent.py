"""AI reasoning and answer generation using Gemini API with resume grounding."""
import logging
import os
from typing import Optional
from config.settings import RESUME_PATH
from engine.parser import extract_resume_profile

logger = logging.getLogger("aetherapply.mcp.ai")

_gemini_client = None


def get_gemini_client():
    """Initializes google-genai client if GEMINI_API_KEY is available."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
        return _gemini_client
    except Exception as e:
        logger.warning("Could not initialize Gemini Client: %s", e)
        return None


def generate_ai_answer(
    question: str,
    job_title: Optional[str] = None,
    job_description: Optional[str] = None,
) -> str:
    """
    Answers complex recruiter/application questions using Gemini API,
    strictly grounded in the candidate's master resume profile.
    """
    profile = extract_resume_profile(RESUME_PATH)
    client = get_gemini_client()

    if client:
        prompt = f"""You are the autonomous job application agent representing Avinash Vishnu Talpade.
You must answer the following job application question accurately, concisely, and professionally based exclusively on his background.

--- CANDIDATE PROFILE ---
Name: {profile.name}
Target Role: Cloud Engineer / DevOps Engineer
Years of Experience: {profile.years_of_experience} years (Accenture, 03/2022 – 08/2025)
Core Skills: {', '.join(sorted(profile.skills))}
Location: {profile.location}

--- RESUME TEXT ---
{profile.raw_text[:2000]}

--- TARGET JOB ---
Job Title: {job_title or 'Cloud / DevOps Role'}
Job Description: {job_description or 'N/A'}

--- QUESTION TO ANSWER ---
{question}

Provide a direct, high-impact response in the first person ("I"). Keep it concise and suitable for an application form box (1-3 short paragraphs max). Do not hallucinate credentials not present in the resume.
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning("Gemini generation failed: %s. Falling back to rule-based response.", e)

    # Fallback response grounded in resume
    q_lower = question.lower()
    if "why" in q_lower or "interest" in q_lower or "fit" in q_lower:
        return (
            f"With over 3.5 years of experience at Accenture maintaining enterprise cloud infrastructure "
            f"across Azure and AWS, I bring strong hands-on expertise in Terraform, Kubernetes, Docker, and CI/CD pipelines. "
            f"My background in DevOps, IaC, and AIOps aligns closely with this {job_title or 'Cloud/DevOps'} opportunity."
        )
    elif "experience" in q_lower or "project" in q_lower:
        return (
            "At Accenture as a Cloud Infrastructure Analyst, I managed high-availability cloud environments, "
            "automated IaC deployments using Terraform, and built automated GitHub Actions and Jenkins pipelines."
        )
    return (
        f"I have 3.5 years of experience specializing in Cloud Infrastructure, DevOps, and Automation (Azure, AWS, Kubernetes, Terraform). "
        f"I am based in Pune and fully authorized to work in India."
    )


def generate_cover_letter(job_title: str, company: str, job_description: Optional[str] = None) -> str:
    """Generates a tailored cover letter based on master resume."""
    profile = extract_resume_profile(RESUME_PATH)
    client = get_gemini_client()

    if client:
        prompt = f"""Write a concise, professional cover letter for Avinash Vishnu Talpade applying for {job_title} at {company}.
Highlight relevant experience at Accenture with Azure, AWS, Kubernetes, Terraform, and CI/CD.
Keep it under 250 words, compelling and structured.

Resume summary:
{profile.raw_text[:1500]}
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning("Gemini cover letter generation failed: %s", e)

    return f"""Dear Hiring Team at {company},

I am writing to express my strong interest in the {job_title} position. With over 3.5 years of experience as a Cloud Infrastructure Analyst at Accenture, I specialize in automating and maintaining resilient enterprise infrastructure across Azure and AWS.

In my recent work, I automated cloud provisioning using Terraform (IaC), orchestrated containerized microservices using Kubernetes and Docker, and established robust CI/CD pipelines with GitHub Actions and Jenkins. My focus is on driving operational excellence, high availability, and incorporating DevSecOps and AIOps practices.

I look forward to discussing how my cloud engineering background can contribute to {company}'s goals.

Sincerely,
Avinash Vishnu Talpade
talpadeavi0303@gmail.com | 8999285015
Pune, Maharashtra, India
https://linkedin.com/in/avinashtalpade
"""
