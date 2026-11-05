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
    "notice_period_days": "15",
    "notice_period_text": "15 Days / Immediate",
    "current_ctc": "900000",
    "current_ctc_lakhs": "9",
    "expected_ctc": "1200000",
    "expected_ctc_lakhs": "12",
    "degree": "Bachelor of Engineering",
    "gender": "Male",
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
    if any(k in text for k in ["how many years", "years of experience", "total experience", "relevant experience"]):
        return "3.5"

    # Notice period
    if "notice period" in text or "serving notice" in text or "joining time" in text:
        if "day" in text:
            return "15"
        return "15 Days"

    # Compensation / CTC questions
    if any(k in text for k in ["current ctc", "current salary", "present ctc", "current compensation"]):
        if "lakh" in text or "inr (lakhs)" in text:
            return "9"
        return "900000"
    if any(k in text for k in ["expected ctc", "expected salary", "desired ctc", "salary expectation"]):
        if "lakh" in text or "inr (lakhs)" in text:
            return "12"
        return "1200000"

    # Authorization / Sponsorship
    if any(k in text for k in ["authorized to work", "legally authorized", "right to work"]):
        return "Yes"
    if any(k in text for k in ["require sponsorship", "visa sponsorship", "need sponsorship", "will you now or in the future require"]):
        return "No"

    # Relocation / Remote / Shift
    if any(k in text for k in ["willing to relocate", "comfortable working in", "open to relocate", "willing to work"]):
        return "Yes"

    # Contact Info
    if "phone" in text or "mobile" in text or "contact number" in text:
        return ANSWERS["phone"]
    if "email" in text or "e-mail" in text:
        return ANSWERS["email"]
    if "city" in text or "current location" in text:
        return "Pune"
    if "current company" in text or "employer" in text or "organization" in text:
        return "Accenture"
    if "current title" in text or "current role" in text or "designation" in text:
        return "Cloud Infrastructure Analyst"
    if "linkedin" in text:
        return ANSWERS["linkedin_url"]
    if "website" in text or "portfolio" in text or "github" in text:
        return ANSWERS["portfolio_url"]
    if "highest education" in text or "degree" in text or "qualification" in text:
        return "Bachelor of Engineering"
    if "gender" in text:
        return "Male"

    return None
