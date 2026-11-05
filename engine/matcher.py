"""Job compatibility matcher against candidate profile."""
import logging
import re
from typing import Dict, List, Set, Tuple
from rapidfuzz import fuzz

from engine.parser import ResumeProfile

logger = logging.getLogger("aetherapply.engine.matcher")


class JobMatcher:
    def __init__(self, profile: ResumeProfile, min_score: float = 60.0):
        self.profile = profile
        self.min_score = min_score

    def match(self, title: str, description: str = "") -> Dict[str, any]:
        """
        Evaluates a job posting against the candidate's master profile.
        Returns score (0-100), matched_skills, and status recommendation.
        """
        title_lower = (title or "").lower().strip()
        desc_lower = (description or "").lower().strip()
        combined_text = f"{title_lower} {desc_lower}"

        # 1. Title match score (0-100)
        title_scores = [fuzz.token_set_ratio(target, title_lower) for target in self.profile.target_titles]
        best_title_score = max(title_scores) if title_scores else 0.0

        # Exact keyword boost for DevOps / Cloud
        if any(term in title_lower for term in ["cloud", "devops", "platform", "sre", "azure", "aws", "infrastructure"]):
            best_title_score = max(best_title_score, 75.0)

        # 2. Skills match score (0-100)
        matched_skills: List[str] = []
        for skill in self.profile.skills:
            # Word boundary matching
            pattern = rf"\b{re.escape(skill)}\b"
            if re.search(pattern, combined_text):
                matched_skills.append(skill)

        # Base skill scoring: 5 or more matched key skills represents high coverage in a job description
        if self.profile.skills:
            # 5 matched skills is considered a full 100% skill match for a single JD snippet
            skill_ratio = min(len(matched_skills) / 5.0, 1.0)
            skill_score = skill_ratio * 100.0
        else:
            skill_score = 50.0

        # Weighted final score:
        # If a detailed description is provided and skills were matched, blend title and skill scores.
        # Otherwise, if only title/snippet is available, score primarily based on title compatibility.
        if len(desc_lower) > 120 and matched_skills:
            final_score = round(0.40 * best_title_score + 0.60 * skill_score, 1)
        else:
            final_score = round(best_title_score, 1)

        # Determine recommendation
        if final_score >= 70.0:
            status = "queued_apply"
        elif final_score >= self.min_score:
            status = "manual_review"
        else:
            status = "rejected"

        return {
            "score": final_score,
            "title_score": best_title_score,
            "skill_score": skill_score,
            "matched_skills": matched_skills,
            "status": status,
        }
