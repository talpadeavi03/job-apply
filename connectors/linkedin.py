"""LinkedIn connector for job search and Easy Apply."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.linkedin")


class LinkedInConnector(BaseConnector):
    def authenticate(self) -> bool:
        # Cloud/Actions runners can run public discovery or use saved cookies if present
        logger.info("LinkedIn connector initialized for public / authenticated search.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        """
        Discovers jobs via public/guest search endpoints or browser context.
        """
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping LinkedIn browser discovery.")
            return []

        search_keywords = self.config.get("search_keywords", ["Cloud Engineer", "DevOps Engineer"])
        locations = self.config.get("locations", ["Pune, India", "Remote"])
        discovered_jobs: List[Dict[str, Any]] = []

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for keyword in search_keywords[:2]:
                for location in locations[:2]:
                    encoded_kw = urllib.parse.quote_plus(keyword)
                    encoded_loc = urllib.parse.quote_plus(location)
                    search_url = (
                        f"https://www.linkedin.com/jobs/search?keywords={encoded_kw}"
                        f"&location={encoded_loc}&f_TPR=r86400"
                    )

                    logger.info("Visiting LinkedIn search: %s in %s", keyword, location)
                    page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    # Extract job cards
                    job_cards = page.query_selector_all(".base-card, .job-search-card")
                    logger.info("Found %d job card elements on LinkedIn page.", len(job_cards))

                    for card in job_cards[:10]:
                        try:
                            title_elem = card.query_selector(".base-search-card__title, h3")
                            company_elem = card.query_selector(".base-search-card__subtitle, h4")
                            loc_elem = card.query_selector(".job-search-card__location")
                            link_elem = card.query_selector("a.base-card__full-link, a")

                            title = title_elem.inner_text().strip() if title_elem else "Cloud/DevOps Role"
                            company = company_elem.inner_text().strip() if company_elem else "Unknown Company"
                            job_loc = loc_elem.inner_text().strip() if loc_elem else location
                            job_url = link_elem.get_attribute("href") if link_elem else None

                            if job_url:
                                job_url = job_url.split("?")[0]

                            discovered_jobs.append({
                                "title": title,
                                "company": company,
                                "platform": "LinkedIn",
                                "location": job_loc,
                                "url": job_url,
                                "description": f"{title} role at {company} located in {job_loc}",
                                "source": "linkedin_search",
                                "source_id": job_url,
                            })
                        except Exception as card_err:
                            logger.debug("Failed to parse individual LinkedIn job card: %s", card_err)

        except Exception as e:
            logger.warning("Error running LinkedIn job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "linkedin_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("LinkedIn auto-apply for '%s' queued for Easy Apply review.", job.get("title"))
        return False
