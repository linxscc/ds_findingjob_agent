import logging

from core.collector import Collector
from core.rate_limiter import RateLimiter
from core.normalizer import Normalizer
from models.job import Job, JobSource, JobInfo, JobLocation, JobContent, JobDates
from models.enums import SourceType
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
logger = logging.getLogger(__name__)


class PlaywrightCollector(Collector):
    """JS 渲染页面采集器（Playwright headless）"""

    def __init__(self, config, rate_limiter: RateLimiter,
                 headless: bool = True, wait_until: str = "networkidle"):
        super().__init__(config)
        self.rate_limiter = rate_limiter
        self.headless = headless
        self.wait_until = wait_until

    def fetch(self) -> list[Job]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install")
            return []

        self.rate_limiter.wait()
        selectors = self.config.selectors or {}
        jobs = []
        seen_urls = set()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(self.config.url, wait_until=self.wait_until, timeout=30000)

            job_list_sel = selectors.get("job_list", "[class*='job'], [data-testid*='job']")
            page.wait_for_selector(job_list_sel, timeout=10000)

            items = page.query_selector_all(job_list_sel)
            for item in items:
                try:
                    title_el = item.query_selector(selectors.get("title", "h2, h3"))
                    loc_el = item.query_selector(selectors.get("location", ""))
                    dept_el = item.query_selector(selectors.get("department", ""))
                    link_el = item.query_selector(selectors.get("link", "a[href]"))

                    title = title_el.inner_text().strip() if title_el else ""
                    link = link_el.get_attribute("href") if link_el else ""

                    if not link or not title:
                        continue

                    if "://" not in link:
                        from urllib.parse import urljoin
                        link = urljoin(self.config.url, link)

                    if link in seen_urls:
                        continue
                    seen_urls.add(link)

                    jobs.append(Job(
                        source=JobSource(
                            type=SourceType.GENERIC_WEB,
                            company_name=self.config.name,
                            company_name_cn=self.config.name_cn,
                            source_url=link,
                            fetched_at=datetime.now(CST).isoformat(),
                        ),
                        job=JobInfo(
                            title=title,
                            department=dept_el.inner_text().strip() if dept_el else "",
                        ),
                        location=JobLocation(
                            city=loc_el.inner_text().strip() if loc_el else "",
                            locations_text=loc_el.inner_text().strip() if loc_el else "",
                        ),
                        content=JobContent(),
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse job item: {e}")
                    continue

            browser.close()

        return jobs
