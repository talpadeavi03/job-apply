"""Form answer engine for common application questions."""
import re
from typing import Optional

# Standard candidate profile answers for Avinash Vishnu Talpade
ANSWERS = {
    "phone": "8999285015",
    "email": "talpadeavi0303@gmail.com",
    "first_name": "Avinash",
    "last_name": "Talpade",
    "full_name": "Avinash Vishnu Talpade",
    "city": "Pune",
    "location": "Pune, Maharashtra, India",
    "country": "India",
    "years_experience": "3.5",
    "notice_period_days": "30",
    "sponsorship_required": False,
    "authorized_to_work": True,
    "willing_to_relocate": True,
    "current_company": "Accenture",
    "current_role": "Cloud Infrastructure Analyst",
    "linkedin_url": "https://www.linkedin.com/in/avinashtalpade",
    "portfolio_url": "https://talpadeavi03.github.io/intro",
}


def get_answer_for_question(label_or_text: str) -> Optional[str]:
    """
    Infers the correct answer for an application form question based on text matching.
    """
    text = (label_or_text or "").lower().strip()

    # Experience questions
    if any(k in text for k in ["how many years", "years of experience", "total experience"]):
        return "3.5"

    # Notice period
    if "notice period" in text:
        if "day" in text:
            return "30"
        return "1 Month"

    # Authorization / Sponsorship
    if any(k in text for k in ["authorized to work", "legally authorized", "right to work"]):
        return "Yes"
    if any(k in text for k in ["require sponsorship", "visa sponsorship", "need sponsorship"]):
        return "No"

    # Relocation / Remote
    if any(k in text for k in ["willing to relocate", "comfortable working in", "open to relocate"]):
        return "Yes"

    # Contact Info
    if "phone" in text or "mobile" in text or "contact number" in text:
        return ANSWERS["phone"]
    if "city" in text or "current location" in text:
        return "Pune"
    if "current company" in text or "employer" in text:
        return "Accenture"
    if "current title" in text or "current role" in text or "designation" in text:
        return "Cloud Infrastructure Analyst"
    if "linkedin" in text:
        return ANSWERS["linkedin_url"]
    if "website" in text or "portfolio" in text:
        return ANSWERS["portfolio_url"]

    return None
