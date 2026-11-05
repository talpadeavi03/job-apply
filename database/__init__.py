"""Database package initialization."""
from database.db import get_session, init_db
from database.firestore import get_firestore_client, save_job_to_firestore
from database.models import ApplicationRecord, Job, ProcessedMessage

__all__ = [
    "get_session",
    "init_db",
    "Job",
    "ApplicationRecord",
    "ProcessedMessage",
    "get_firestore_client",
    "save_job_to_firestore",
]
