"""Connector registry and factory."""
import logging
from typing import Any, Dict, List, Optional
from browser.manager import BrowserManager
from connectors.base import BaseConnector
from connectors.gmail import GmailConnector
from connectors.linkedin import LinkedInConnector
from connectors.naukri import NaukriConnector

logger = logging.getLogger("aetherapply.connectors.registry")

CONNECTOR_CLASSES = {
    "gmail": GmailConnector,
    "linkedin": LinkedInConnector,
    "naukri": NaukriConnector,
}


def get_active_connectors(
    platforms_config: Dict[str, Any],
    browser_manager: Optional[BrowserManager] = None,
) -> List[BaseConnector]:
    """
    Instantiates all enabled connectors found in platforms_config.
    """
    platforms = platforms_config.get("platforms", {})
    connectors: List[BaseConnector] = []

    for platform_key, conf in platforms.items():
        if not conf.get("enabled", False):
            continue

        connector_cls = CONNECTOR_CLASSES.get(platform_key.lower())
        if connector_cls:
            try:
                instance = connector_cls(config=conf, browser_manager=browser_manager)
                connectors.append(instance)
                logger.info("Loaded connector: %s", conf.get("name", platform_key))
            except Exception as e:
                logger.error("Failed to load connector %s: %s", platform_key, e)
        else:
            logger.debug("No connector implementation yet for %s", platform_key)

    return connectors
