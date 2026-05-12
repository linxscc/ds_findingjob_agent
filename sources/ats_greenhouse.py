import logging
import requests

from core.collector import Collector
from core.rate_limiter import RateLimiter
from core.normalizer import Normalizer
from models.job import Job

logger = logging.getLogger(__name__)


class GreenhouseCollector(Collector):
    """Greenhouse 公开 API 采集器

    Greenhouse API 不支持按地点预过滤，拉取全量后客户端过滤。
    """

    BASE = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, config, rate_limiter: RateLimiter):
        super().__init__(config)
        self.rate_limiter = rate_limiter

    def fetch(self) -> list[Job]:
        url = f"{self.BASE}/{self.config.board_token}/jobs?content=true"
        self.rate_limiter.wait()
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 404:
                logger.warning(f"  Greenhouse board '{self.config.board_token}' returned 404. Check board_token.")
                return []
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"  Greenhouse API error for {self.config.name}: {e}")
            return []

        jobs = []
        for raw in data.get("jobs", []):
            job = Normalizer.normalize_greenhouse(raw, self.config)
            if job:
                jobs.append(job)
        return jobs
