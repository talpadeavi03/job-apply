"""Naukri connector for job discovery and apply flow."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.naukri")


class NaukriConnector(BaseConnector):
    def authenticate(self) -> bool:
        logger.info("Naukri connector ready.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping Naukri discovery.")
            return []

        search_keywords = self.config.get("search_keywords", ["Cloud Engineer", "DevOps"])
        discovered_jobs: List[Dict[str, Any]] = []

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for keyword in search_keywords[:1]:
                slug = keyword.lower().replace(" ", "-")
                search_url = f"https://www.naukri.com/{slug}-jobs-in-pune"

                logger.info("Visiting Naukri: %s", search_url)
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                job_tuples = page.query_selector_all(".srp-jobtuple-wrapper, .cust-job-tuple")
                logger.info("Found %d job card elements on Naukri page.", len(job_tuples))

                for item in job_tuples[:10]:
                    try:
                        title_el = item.query_selector("a.title")
                        comp_el = item.query_selector("a.comp-name")
                        loc_el = item.query_selector(".locWdth, .loc-wrap")

                        title = title_el.inner_text().strip() if title_el else keyword
                        url = title_el.get_attribute("href") if title_el else None
                        company = comp_el.inner_text().strip() if comp_el else "Confidential"
                        location = loc_el.inner_text().strip() if loc_el else "Pune"

                        discovered_jobs.append({
                            "title": title,
                            "company": company,
                            "platform": "Naukri",
                            "location": location,
                            "url": url,
                            "description": f"{title} at {company} in {location}",
                            "source": "naukri_search",
                            "source_id": url,
                        })
                    except Exception as card_err:
                        logger.debug("Failed parsing Naukri item: %s", card_err)

        except Exception as e:
            logger.warning("Error running Naukri job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "naukri_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("Naukri apply requested for %s.", job.get("title"))
        return False
