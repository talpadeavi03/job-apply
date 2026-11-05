"""Foundit (formerly Monster India) connector for job discovery."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.foundit")


class FounditConnector(BaseConnector):
    def authenticate(self) -> bool:
        logger.info("Foundit connector ready.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping Foundit discovery.")
            return []

        search_keywords = self.config.get("search_keywords", ["Cloud Engineer", "DevOps"])
        locations = self.config.get("locations", ["Pune"])
        discovered_jobs: List[Dict[str, Any]] = []

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for keyword in search_keywords[:1]:
                for location in locations[:1]:
                    kw_enc = urllib.parse.quote_plus(keyword)
                    loc_enc = urllib.parse.quote_plus(location)
                    search_url = f"https://www.foundit.in/srp/results?query={kw_enc}&locations={loc_enc}"

                    logger.info("Visiting Foundit: %s", search_url)
                    page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)

                    # Scan for job cards
                    job_cards = page.query_selector_all(".cardContainer, .srpResultCard, [class*='jobCard']")
                    logger.info("Found %d job card elements on Foundit.", len(job_cards))

                    for card in job_cards[:15]:
                        try:
                            title_el = card.query_selector(".jobTitle, [class*='title'], h3")
                            comp_el = card.query_selector(".companyName, [class*='company']")
                            loc_el = card.query_selector(".location, [class*='location']")
                            link_el = card.query_selector("a[href*='/job/'], a")

                            title = title_el.inner_text().strip() if title_el else keyword
                            company = comp_el.inner_text().strip() if comp_el else "Foundit Employer"
                            job_loc = loc_el.inner_text().strip() if loc_el else location
                            raw_href = link_el.get_attribute("href") if link_el else ""
                            job_url = urllib.parse.urljoin("https://www.foundit.in", raw_href).split("?")[0] if raw_href else None

                            discovered_jobs.append({
                                "title": title,
                                "company": company,
                                "platform": "Foundit",
                                "location": job_loc,
                                "url": job_url,
                                "description": f"{title} at {company} in {job_loc}",
                                "source": "foundit_search",
                                "source_id": job_url,
                            })
                        except Exception as c_err:
                            logger.debug("Error parsing Foundit card: %s", c_err)

        except Exception as e:
            logger.warning("Error running Foundit job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "foundit_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("Foundit apply requested for %s", job.get("title"))
        return False
