import logging
import requests

from core.collector import Collector
from core.rate_limiter import RateLimiter
from core.normalizer import Normalizer
from models.job import Job

logger = logging.getLogger(__name__)


class LeverCollector(Collector):
    """Lever 公开 API 采集器

    Lever API 支持 ?location= 和 ?team= 参数预过滤。
    每个站点先用中国城市名尝试预过滤，无结果则拉全量后客户端过滤。
    """

    BASE = "https://api.lever.co/v0/postings"

    def __init__(self, config, rate_limiter: RateLimiter):
        super().__init__(config)
        self.rate_limiter = rate_limiter

    def fetch(self) -> list[Job]:
        # 尝试用 China 地点做 API 预过滤，减少无关数据
        china_locs = self.config.china_locations or []
        jobs = []

        for loc in china_locs:
            if loc.lower() in ("remote",):
                continue
            batch = self._fetch_page(f"?mode=json&location={loc}")
            jobs.extend(batch)

        # 如果预过滤没拿到结果，回退到拉取全量
        if not jobs:
            logger.info(f"  No results with China location filter, fetching all for {self.config.name}")
            jobs = self._fetch_page("?mode=json")

        # 去重（同一个 job 可能匹配多个 location）
        seen = set()
        unique = []
        for job in jobs:
            key = job.source.external_id or job.source.source_url
            if key in seen:
                continue
            seen.add(key)
            unique.append(job)
        return unique

    def _fetch_page(self, query: str) -> list[Job]:
        url = f"{self.BASE}/{self.config.site}{query}"
        self.rate_limiter.wait()
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 404:
                logger.warning(f"  Lever site '{self.config.site}' returned 404. Check the site name.")
                return []
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"  Lever API error for {self.config.name}: {e}")
            return []

        results = []
        for raw in data:
            job = Normalizer.normalize_lever(raw, self.config)
            if job:
                results.append(job)
        return results
