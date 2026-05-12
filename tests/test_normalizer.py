import pytest
from models.enums import SourceType, WorkplaceType, EmploymentType
from core.normalizer import Normalizer


class TestNormalizer:
    def test_strip_html(self):
        assert Normalizer._strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_detect_chinese_language(self):
        assert Normalizer._detect_language("高级软件开发工程师") == "zh"

    def test_detect_english_language(self):
        assert Normalizer._detect_language("Senior Software Engineer") == "en"

    def test_infer_workplace_remote(self):
        assert Normalizer._infer_workplace_type(["Remote", "China"]) == WorkplaceType.REMOTE

    def test_infer_workplace_onsite(self):
        assert Normalizer._infer_workplace_type(["Shanghai", "Beijing"]) == WorkplaceType.ON_SITE

    def test_infer_employment_intern(self):
        assert Normalizer._infer_employment_type("Software Engineer Intern") == EmploymentType.INTERN

    def test_infer_country_cn(self):
        assert Normalizer._infer_country(["Beijing", "Shanghai"]) == "CN"
        assert Normalizer._infer_country(["San Francisco", "New York"]) == ""
