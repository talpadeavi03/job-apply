"""Abstract Base Connector interface for all job platforms."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from browser.manager import BrowserManager


class BaseConnector(ABC):
    """
    Standard interface that all platform connectors (Gmail, LinkedIn, Naukri, etc.)
    must implement.
    """

    def __init__(self, config: Dict[str, Any], browser_manager: Optional[BrowserManager] = None):
        self.config = config
        self.browser_manager = browser_manager
        self.name: str = config.get("name", self.__class__.__name__)
        self.enabled: bool = config.get("enabled", True)

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticates with the platform (via API tokens, cookies, or credentials)."""
        pass

    @abstractmethod
    def discover_jobs(self) -> List[Dict[str, Any]]:
        """
        Discovers new jobs. Returns a list of standardized job dictionaries:
        {
            "title": str,
            "company": str,
            "platform": str,
            "location": Optional[str],
            "url": Optional[str],
            "description": Optional[str],
            "source": str,
            "source_id": Optional[str],
        }
        """
        pass

    @abstractmethod
    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        """Applies to a job on the platform."""
        pass

    def logout(self) -> None:
        """Optional cleanup or session termination."""
        pass
