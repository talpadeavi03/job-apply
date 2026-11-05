"""Hirist connector for tech and DevOps job discovery."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.hirist")


class HiristConnector(BaseConnector):
    def authenticate(self) -> bool:
        logger.info("Hirist connector ready.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping Hirist discovery.")
            return []

        discovered_jobs: List[Dict[str, Any]] = []
        target_urls = [
            "https://www.hirist.tech/k/devops-jobs.html",
            "https://www.hirist.tech/k/cloud-computing-jobs.html",
        ]

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for search_url in target_urls:
                logger.info("Visiting Hirist: %s", search_url)
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Query job cards or links
                cards = page.query_selector_all(".job-list-card, .job-item, .card, [class*='jobCard']")
                logger.info("Found %d job card elements on Hirist.", len(cards))

                for card in cards[:15]:
                    try:
                        title_el = card.query_selector(".job-title, [class*='title'], h3")
                        comp_el = card.query_selector(".company-name, [class*='company']")
                        loc_el = card.query_selector(".job-loc, [class*='location']")
                        link_el = card.query_selector("a[href*='/j/'], a")

                        title = title_el.inner_text().strip() if title_el else "DevOps / Cloud Role"
                        company = comp_el.inner_text().strip() if comp_el else "Hirist Tech"
                        job_loc = loc_el.inner_text().strip() if loc_el else "India / Remote"
                        raw_href = link_el.get_attribute("href") if link_el else ""
                        job_url = urllib.parse.urljoin("https://www.hirist.tech", raw_href).split("?")[0] if raw_href else None

                        discovered_jobs.append({
                            "title": title,
                            "company": company,
                            "platform": "Hirist",
                            "location": job_loc,
                            "url": job_url,
                            "description": f"{title} at {company} in {job_loc}",
                            "source": "hirist_search",
                            "source_id": job_url,
                        })
                    except Exception as c_err:
                        logger.debug("Error parsing Hirist card: %s", c_err)

        except Exception as e:
            logger.warning("Error running Hirist job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "hirist_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("Hirist apply requested for %s", job.get("title"))
        return False
