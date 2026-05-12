import pytest
from unittest.mock import MagicMock, patch
from models.source import SourceConfig
from models.enums import SourceType, WorkplaceType
from core.rate_limiter import RateLimiter
from sources.ats_greenhouse import GreenhouseCollector
from sources.ats_lever import LeverCollector
from sources.ats_workday import WorkdayCollector


class TestGreenhouseCollector:
    @patch("sources.ats_greenhouse.requests.get")
    def test_fetch_parses_jobs(self, mock_get):
        mock_get.return_value.json.return_value = {
            "jobs": [{
                "id": 12345,
                "title": "Software Engineer",
                "absolute_url": "https://example.com/jobs/12345",
                "location": {"name": "Beijing"},
                "content": "<p>Write code</p>",
                "departments": [{"name": "Engineering"}],
                "offices": [{"name": "Beijing"}],
                "updated_at": "2026-05-01T00:00:00Z",
            }]
        }
        mock_get.return_value.raise_for_status.return_value = None

        config = SourceConfig(
            name="Test", name_cn="测试", type=SourceType.GREENHOUSE,
            url="https://example.com", board_token="test",
        )
        collector = GreenhouseCollector(config, RateLimiter(0))
        jobs = collector.fetch()

        assert len(jobs) == 1
        assert jobs[0].job.title == "Software Engineer"
        assert jobs[0].location.city == "Beijing"
        assert jobs[0].source.type == SourceType.GREENHOUSE


class TestLeverCollector:
    @patch("sources.ats_lever.requests.get")
    def test_fetch_parses_jobs(self, mock_get):
        mock_get.return_value.json.return_value = [{
            "id": "abc-123",
            "text": "Senior Backend Engineer",
            "categories": {
                "team": "Engineering",
                "location": "Shanghai",
                "department": "Tech",
                "commitment": "Full-time",
                "allLocations": ["Shanghai", "China"],
            },
            "country": "CN",
            "hostedUrl": "https://jobs.lever.co/test/abc-123",
            "descriptionPlain": "Build backend services",
            "workplaceType": "hybrid",
            "created_at": 1715500000000,
        }]
        mock_get.return_value.raise_for_status.return_value = None

        config = SourceConfig(
            name="Test", name_cn="测试", type=SourceType.LEVER,
            url="https://jobs.lever.co/test", site="test",
        )
        collector = LeverCollector(config, RateLimiter(0))
        jobs = collector.fetch()

        assert len(jobs) == 1
        assert jobs[0].job.title == "Senior Backend Engineer"
        assert jobs[0].job.workplace_type == WorkplaceType.HYBRID
        assert jobs[0].location.country == "CN"
