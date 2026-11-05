"""Resume uploader for Playwright file inputs."""
import logging
from pathlib import Path
from typing import Optional
from playwright.sync_api import Page
from config.settings import RESUME_PATH

logger = logging.getLogger("aetherapply.application.uploader")


def upload_resume(page: Page, resume_path: Optional[Path] = None, selector: str = "input[type='file']") -> bool:
    """
    Finds the file upload input and sets the resume file.
    """
    path_to_upload = resume_path or RESUME_PATH
    if not path_to_upload.exists():
        logger.error("Resume file not found at %s", path_to_upload)
        return False

    try:
        file_input = page.query_selector(selector)
        if file_input:
            file_input.set_input_files(str(path_to_upload))
            logger.info("Uploaded resume: %s", path_to_upload.name)
            return True
        logger.debug("No file input selector matching %s found on page.", selector)
        return False
    except Exception as e:
        logger.warning("Failed to upload resume to %s: %s", selector, e)
        return False
