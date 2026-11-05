"""Resume parser extracting profile and skills from PDF."""
import logging
from pathlib import Path
from typing import Any, Dict, List, Set
import pypdf

from config.settings import (
    CANDIDATE_EMAIL,
    CANDIDATE_LOCATION,
    CANDIDATE_NAME,
    CANDIDATE_PHONE,
    RESUME_PATH,
)

logger = logging.getLogger("aetherapply.engine.parser")

CORE_SKILLS: Set[str] = {
    "azure",
    "aws",
    "devsecops",
    "devops",
    "aiops",
    "mlops",
    "docker",
    "kubernetes",
    "helm",
    "github actions",
    "jenkins",
    "ci/cd",
    "terraform",
    "ansible",
    "iac",
    "infrastructure as code",
    "python",
    "powershell",
    "bash",
    "git",
    "gitlab",
    "linux",
    "ubuntu",
    "rhel",
    "prometheus",
    "grafana",
    "cloudwatch",
    "postgresql",
    "mysql",
    "microsoft sentinel",
    "iam",
    "rbac",
}

TARGET_TITLES: List[str] = [
    "cloud engineer",
    "devops engineer",
    "cloud infrastructure analyst",
    "site reliability engineer",
    "sre",
    "platform engineer",
    "infrastructure engineer",
    "azure cloud engineer",
    "aws cloud engineer",
]


class ResumeProfile:
    def __init__(
        self,
        name: str = CANDIDATE_NAME,
        email: str = CANDIDATE_EMAIL,
        phone: str = CANDIDATE_PHONE,
        location: str = CANDIDATE_LOCATION,
        skills: Set[str] = CORE_SKILLS,
        target_titles: List[str] = TARGET_TITLES,
        years_of_experience: float = 3.5,
        raw_text: str = "",
    ):
        self.name = name
        self.email = email
        self.phone = phone
        self.location = location
        self.skills = skills
        self.target_titles = target_titles
        self.years_of_experience = years_of_experience
        self.raw_text = raw_text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "skills": sorted(list(self.skills)),
            "target_titles": self.target_titles,
            "years_of_experience": self.years_of_experience,
        }


def extract_resume_profile(pdf_path: Path = RESUME_PATH) -> ResumeProfile:
    """Extracts raw text and parsed profile from the master PDF resume."""
    raw_text = ""
    if pdf_path.exists():
        try:
            reader = pypdf.PdfReader(str(pdf_path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            raw_text = "\n".join(pages_text)
            logger.info("Successfully extracted %d characters from %s", len(raw_text), pdf_path.name)
        except Exception as e:
            logger.error("Failed to parse resume PDF %s: %s", pdf_path, e)
    else:
        logger.warning("Resume file not found at %s. Using default profile.", pdf_path)

    return ResumeProfile(
        name=CANDIDATE_NAME,
        email=CANDIDATE_EMAIL,
        phone=CANDIDATE_PHONE,
        location=CANDIDATE_LOCATION,
        skills=CORE_SKILLS,
        target_titles=TARGET_TITLES,
        years_of_experience=3.5,
        raw_text=raw_text,
    )
