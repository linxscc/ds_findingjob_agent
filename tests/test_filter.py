import pytest
from models.enums import MatchLevel, SourceType, WorkplaceType, EmploymentType
from models.job import Job, JobSource, JobInfo, JobLocation, JobContent, FilterResult
from core.filter import JobFilter


def make_job(title: str, desc: str = "", city: str = "Beijing", country: str = "CN"):
    return Job(
        source=JobSource(type=SourceType.MANUAL, company_name="TestCo", company_name_cn="测试公司", source_url=""),
        job=JobInfo(title=title),
        location=JobLocation(city=city, country=country),
        content=JobContent(description_plain=desc),
    )


class TestJobFilter:
    def setup_method(self):
        self.filter = JobFilter(
            title_keywords=["software engineer", "backend developer", "python", "软件工程师", "后端开发"],
            skill_keywords=["python", "react", "aws", "django"],
            china_only=True,
            allow_remote_china=True,
        )

    def test_china_location_passes(self):
        assert self.filter.should_process(make_job("Test", city="Shanghai")) is True
        assert self.filter.should_process(make_job("Test", city="北京")) is True

    def test_non_china_blocked(self):
        assert self.filter.should_process(make_job("Test", city="New York", country="US")) is False

    def test_remote_china_allowed(self):
        assert self.filter.should_process(make_job("Test", city="Remote China", country="US")) is True

    def test_strong_match_title(self):
        result = self.filter.evaluate(make_job("Senior Software Engineer", "python aws react"))
        assert result.match_level == MatchLevel.STRONG
        assert result.is_software_role is True

    def test_partial_match_skills_only(self):
        result = self.filter.evaluate(make_job("Product Manager", "experience with python and aws"))
        assert result.match_level == MatchLevel.PARTIAL

    def test_no_match(self):
        result = self.filter.evaluate(make_job("Sales Manager", "responsible for revenue"))
        assert result.match_level == MatchLevel.NONE

    def test_chinese_title_keyword(self):
        result = self.filter.evaluate(make_job("高级后端开发工程师", "python django"))
        assert result.match_level == MatchLevel.STRONG
