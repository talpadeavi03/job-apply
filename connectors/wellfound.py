"""Wellfound (formerly AngelList Talent) connector for startup and remote jobs."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.wellfound")


class WellfoundConnector(BaseConnector):
    def authenticate(self) -> bool:
        logger.info("Wellfound connector initialized.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping Wellfound discovery.")
            return []

        role_slugs = ["devops-engineer", "cloud-engineer"]
        discovered_jobs: List[Dict[str, Any]] = []

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for slug in role_slugs:
                search_url = f"https://wellfound.com/role/l/{slug}/remote"
                logger.info("Visiting Wellfound: %s", search_url)
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Query job links
                job_links = page.query_selector_all("a[href*='/jobs/']")
                logger.info("Found %d job links on Wellfound page.", len(job_links))

                seen_urls = set()
                for link in job_links[:15]:
                    try:
                        href = link.get_attribute("href")
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        full_url = urllib.parse.urljoin("https://wellfound.com", href).split("?")[0]
                        text = link.inner_text().strip()
                        title = text if text and len(text) > 3 else slug.replace("-", " ").title()

                        discovered_jobs.append({
                            "title": title,
                            "company": "Startup",
                            "platform": "Wellfound",
                            "location": "Remote",
                            "url": full_url,
                            "description": f"{title} remote startup role on Wellfound",
                            "source": "wellfound_search",
                            "source_id": full_url,
                        })
                    except Exception as c_err:
                        logger.debug("Error parsing Wellfound card: %s", c_err)

        except Exception as e:
            logger.warning("Error running Wellfound job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "wellfound_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("Wellfound apply flow queued for %s", job.get("title"))
        return False
