import logging
import requests

from core.collector import Collector
from core.rate_limiter import RateLimiter
from core.normalizer import Normalizer
from models.job import Job

logger = logging.getLogger(__name__)


class WorkdayCollector(Collector):
    """Workday CXS API 采集器（半公开 POST API）

    使用 searchText 预过滤中国城市，减少返回量。
    """

    def __init__(self, config, rate_limiter: RateLimiter):
        super().__init__(config)
        self.rate_limiter = rate_limiter

    def _base_url(self) -> str:
        c = self.config
        return f"https://{c.tenant}.{c.wd_server}.myworkdayjobs.com/wday/cxs/{c.tenant}/{c.site}"

    def fetch(self) -> list[Job]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
        }

        # 用中国城市名做搜索预过滤
        search_terms = ["China", "Beijing", "Shanghai", "Shenzhen"]
        all_jobs = []
        seen_ids = set()

        for term in search_terms:
            offset = 0
            limit = 20
            while True:
                self.rate_limiter.wait()
                try:
                    resp = requests.post(
                        f"{self._base_url()}/jobs",
                        json={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": term},
                        headers=headers,
                        timeout=30,
                    )
                    if resp.status_code == 404:
                        logger.warning(f"  Workday site '{self.config.site}' returned 404. Check tenant/wd_server/site.")
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException as e:
                    logger.error(f"  Workday API error for {self.config.name}: {e}")
                    break

                batch = data.get("jobPostings", [])
                if not batch:
                    break

                for raw in batch:
                    ext_id = raw.get("externalPath", "")
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    job = Normalizer.normalize_workday(raw, self.config)
                    if job:
                        all_jobs.append(job)

                total = data.get("total", 0)
                offset += limit
                if offset >= total:
                    break

            # 如果该搜索词有结果就不再尝试后续词
            if all_jobs:
                break

        # 如果预过滤无结果，回退到拉全量
        if not all_jobs:
            logger.info(f"  No results with China search, fetching all for {self.config.name}")
            offset = 0
            while True:
                self.rate_limiter.wait()
                try:
                    resp = requests.post(
                        f"{self._base_url()}/jobs",
                        json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""},
                        headers=headers,
                        timeout=30,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException:
                    break

                batch = data.get("jobPostings", [])
                if not batch:
                    break
                for raw in batch:
                    ext_id = raw.get("externalPath", "")
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)
                    job = Normalizer.normalize_workday(raw, self.config)
                    if job:
                        all_jobs.append(job)

                total = data.get("total", 0)
                offset += 20
                if offset >= total:
                    break

        return all_jobs
