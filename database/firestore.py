"""Firebase Cloud Firestore integration for AetherApply."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aetherapply.database.firestore")

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None

_firestore_client = None


def get_firestore_client():
    """
    Initializes and returns the Firebase Firestore client.
    Looks for:
    1. FIREBASE_SERVICE_ACCOUNT environment variable (JSON string or path to JSON file).
    2. Local file 'firebase-service-account.json'.
    3. Returns None if unconfigured.
    """
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError:
        logger.warning("firebase-admin is not installed. Firestore disabled.")
        return None

    # Check already initialized apps
    if firebase_admin._apps:
        _firestore_client = firestore.client()
        return _firestore_client

    sa_env = os.getenv("FIREBASE_SERVICE_ACCOUNT", "").strip()
    cred = None

    if sa_env:
        if sa_env.startswith("{") and sa_env.endswith("}"):
            try:
                cert_dict = json.loads(sa_env)
                cred = credentials.Certificate(cert_dict)
                logger.info("Loaded Firebase credentials from JSON environment variable.")
            except Exception as e:
                logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT JSON: %s", e)
        elif Path(sa_env).exists():
            cred = credentials.Certificate(sa_env)
            logger.info("Loaded Firebase credentials from file: %s", sa_env)

    if not cred:
        local_sa = Path("firebase-service-account.json")
        if local_sa.exists():
            cred = credentials.Certificate(str(local_sa))
            logger.info("Loaded Firebase credentials from local file: %s", local_sa)

    if not cred:
        logger.debug("No Firebase credentials provided. Running without Firestore.")
        return None

    try:
        firebase_admin.initialize_app(cred)
        _firestore_client = firestore.client()
        logger.info("Successfully connected to Firebase Cloud Firestore.")
        return _firestore_client
    except Exception as e:
        logger.error("Error initializing Firebase App: %s", e)
        return None


def save_job_to_firestore(job_data: Dict[str, Any]) -> bool:
    """Saves or updates a job document in the 'jobs' collection using job_hash as document ID."""
    db = get_firestore_client()
    if not db:
        return False

    job_hash = job_data.get("job_hash")
    if not job_hash:
        return False

    try:
        doc_ref = db.collection("jobs").document(job_hash)
        doc_data = {
            "title": job_data.get("title", ""),
            "company": job_data.get("company", ""),
            "platform": job_data.get("platform", ""),
            "location": job_data.get("location"),
            "url": job_data.get("url"),
            "match_score": float(job_data.get("match_score", 0.0)),
            "status": job_data.get("status", "discovered"),
            "source": job_data.get("source", "connector"),
            "source_id": job_data.get("source_id"),
            "description": job_data.get("description", "")[:5000] if job_data.get("description") else None,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        # Set with merge to preserve created_at if it exists
        doc = doc_ref.get()
        if not doc.exists:
            doc_data["created_at"] = firestore.SERVER_TIMESTAMP

        doc_ref.set(doc_data, merge=True)
        return True
    except Exception as e:
        logger.error("Error saving job %s to Firestore: %s", job_hash, e)
        return False


def get_all_firestore_job_hashes() -> set:
    """Returns a set of all job hashes already stored in Firestore."""
    db = get_firestore_client()
    if not db:
        return set()

    try:
        docs = db.collection("jobs").select([]).stream()
        return {doc.id for doc in docs}
    except Exception as e:
        logger.error("Error fetching job hashes from Firestore: %s", e)
        return set()
