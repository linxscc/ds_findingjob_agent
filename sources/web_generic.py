import requests
from bs4 import BeautifulSoup

from core.collector import Collector
from core.rate_limiter import RateLimiter
from core.normalizer import Normalizer
from models.job import Job, JobSource, JobInfo, JobLocation, JobContent, JobDates
from models.enums import SourceType
from datetime import datetime, timezone, timedelta


CST = timezone(timedelta(hours=8))


class GenericWebCollector(Collector):
    """通用 HTML 页面采集器（requests + BS4）"""

    def __init__(self, config, rate_limiter: RateLimiter):
        super().__init__(config)
        self.rate_limiter = rate_limiter

    def fetch(self) -> list[Job]:
        self.rate_limiter.wait()
        resp = requests.get(
            self.config.url,
            headers={"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")},
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        selectors = self.config.selectors or {}
        job_list_sel = selectors.get("job_list", "a[href]")

        jobs = []
        seen_urls = set()

        for item in soup.select(job_list_sel):
            try:
                title_el = item.select_one(selectors.get("title", "h2, h3"))
                loc_el = item.select_one(selectors.get("location", ""))
                dept_el = item.select_one(selectors.get("department", ""))
                link_el = item if item.name == "a" else item.select_one("a[href]")

                title = title_el.get_text(strip=True) if title_el else ""
                link = link_el.get("href", "") if link_el else ""

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
                        department=dept_el.get_text(strip=True) if dept_el else "",
                    ),
                    location=JobLocation(
                        city=loc_el.get_text(strip=True) if loc_el else "",
                        locations_text=loc_el.get_text(strip=True) if loc_el else "",
                    ),
                    content=JobContent(),
                ))
            except Exception:
                continue

        return jobs
