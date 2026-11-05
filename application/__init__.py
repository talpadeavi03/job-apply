"""Application automation package."""
from application.answers import ANSWERS, get_answer_for_question
from application.apply import AutoApplier
from application.linkedin_applier import LinkedInApplier
from application.universal_form_applier import UniversalFormApplier
from application.uploader import upload_resume

__all__ = [
    "ANSWERS",
    "AutoApplier",
    "LinkedInApplier",
    "UniversalFormApplier",
    "get_answer_for_question",
    "upload_resume",
]
