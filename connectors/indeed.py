"""Indeed connector for job discovery."""
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
from connectors.base import BaseConnector

logger = logging.getLogger("aetherapply.connectors.indeed")


class IndeedConnector(BaseConnector):
    def authenticate(self) -> bool:
        logger.info("Indeed connector initialized.")
        return True

    def discover_jobs(self) -> List[Dict[str, Any]]:
        if not self.browser_manager:
            logger.warning("BrowserManager not provided. Skipping Indeed discovery.")
            return []

        search_keywords = self.config.get("search_keywords", ["Cloud Engineer", "DevOps Engineer"])
        locations = self.config.get("locations", ["Pune", "Remote"])
        discovered_jobs: List[Dict[str, Any]] = []

        context = self.browser_manager.new_context()
        page = context.new_page()

        try:
            for keyword in search_keywords[:2]:
                for location in locations[:2]:
                    kw_enc = urllib.parse.quote_plus(keyword)
                    loc_enc = urllib.parse.quote_plus(location)
                    search_url = f"https://in.indeed.com/jobs?q={kw_enc}&l={loc_enc}"

                    logger.info("Visiting Indeed: %s in %s", keyword, location)
                    page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    cards = page.query_selector_all(".job_seen_beacon, .resultContent")
                    logger.info("Found %d job card elements on Indeed.", len(cards))

                    for card in cards[:15]:
                        try:
                            title_el = card.query_selector("h2.jobTitle, a[data-jk]")
                            comp_el = card.query_selector("[data-testid='company-name']")
                            loc_el = card.query_selector("[data-testid='text-location']")
                            link_el = card.query_selector("a[data-jk], h2.jobTitle a")

                            jk = link_el.get_attribute("data-jk") if link_el else None
                            if jk:
                                job_url = f"https://in.indeed.com/viewjob?jk={jk}"
                            elif link_el:
                                raw_href = link_el.get_attribute("href") or ""
                                job_url = urllib.parse.urljoin("https://in.indeed.com", raw_href).split("&")[0]
                            else:
                                job_url = None

                            title = title_el.inner_text().strip() if title_el else keyword
                            company = comp_el.inner_text().strip() if comp_el else "Employer"
                            job_loc = loc_el.inner_text().strip() if loc_el else location

                            discovered_jobs.append({
                                "title": title,
                                "company": company,
                                "platform": "Indeed",
                                "location": job_loc,
                                "url": job_url,
                                "description": f"{title} at {company} in {job_loc}",
                                "source": "indeed_search",
                                "source_id": jk or job_url,
                            })
                        except Exception as c_err:
                            logger.debug("Error parsing Indeed card: %s", c_err)

        except Exception as e:
            logger.warning("Error running Indeed job discovery: %s", e)
            self.browser_manager.take_screenshot(page, "indeed_error")
        finally:
            page.close()
            context.close()

        return discovered_jobs

    def apply(self, job: Dict[str, Any], resume_path: Optional[str] = None) -> bool:
        logger.info("Indeed apply flow queued for %s", job.get("title"))
        return False
