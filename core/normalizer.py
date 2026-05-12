import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from models.enums import SourceType, WorkplaceType, EmploymentType
from models.job import Job, JobSource, JobInfo, JobLocation, JobContent, JobCompensation, JobDates, FilterResult


CST = timezone(timedelta(hours=8))

CHINA_CITIES = [
    "Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Hangzhou", "Chengdu",
    "Nanjing", "Wuhan", "Suzhou", "Xi'an", "Tianjin", "Chongqing", "Dalian",
    "Qingdao", "Xiamen", "Hefei", "Changsha", "Ningbo", "Fuzhou", "Kunming",
    "Shenyang", "Wuxi", "Jinan", "Zhengzhou", "Dongguan", "Zhuhai",
    "北京", "上海", "深圳", "广州", "杭州", "成都", "南京", "武汉", "苏州",
    "西安", "天津", "重庆", "大连", "青岛", "厦门", "合肥", "长沙",
    "Remote China", "China", "China Mainland", "中国", "远程",
]


class Normalizer:
    """将各源原始数据统一转换为 Job 模型"""

    @staticmethod
    def normalize_greenhouse(raw: dict, config) -> Optional[Job]:
        try:
            location_name = raw.get("location", {}).get("name", "")
            offices = raw.get("offices", [])
            all_locations = [o.get("name", "") for o in offices]

            return Job(
                source=JobSource(
                    type=SourceType.GREENHOUSE,
                    company_name=config.name,
                    company_name_cn=config.name_cn,
                    source_url=raw.get("absolute_url", ""),
                    external_id=str(raw.get("id", "")),
                    fetched_at=datetime.now(CST).isoformat(),
                ),
                job=JobInfo(
                    title=raw.get("title", ""),
                    department=", ".join(d.get("name", "") for d in raw.get("departments", [])),
                    workplace_type=Normalizer._infer_workplace_type(all_locations),
                    employment_type=Normalizer._infer_employment_type(raw.get("title", "")),
                ),
                location=JobLocation(
                    city=location_name,
                    country=Normalizer._infer_country(all_locations),
                    locations_text=", ".join(all_locations),
                ),
                content=JobContent(
                    description_html=raw.get("content", ""),
                    description_plain=Normalizer._strip_html(raw.get("content", "")),
                ),
                dates=JobDates(
                    posted_on=raw.get("updated_at", "")[:10] if raw.get("updated_at") else "",
                ),
                language=Normalizer._detect_language(raw.get("title", "")),
            )
        except Exception:
            return None

    @staticmethod
    def normalize_lever(raw: dict, config) -> Optional[Job]:
        try:
            categories = raw.get("categories", {})
            loc_text = categories.get("location", "")
            all_locations = categories.get("allLocations", [loc_text])

            return Job(
                source=JobSource(
                    type=SourceType.LEVER,
                    company_name=config.name,
                    company_name_cn=config.name_cn,
                    source_url=raw.get("hostedUrl", ""),
                    external_id=raw.get("id", ""),
                    fetched_at=datetime.now(CST).isoformat(),
                ),
                job=JobInfo(
                    title=raw.get("text", ""),
                    department=categories.get("department", ""),
                    team=categories.get("team", ""),
                    workplace_type=Normalizer._parse_workplace_type(raw.get("workplaceType", "unspecified")),
                    employment_type=Normalizer._infer_employment_type(categories.get("commitment", "")),
                ),
                location=JobLocation(
                    city=loc_text,
                    country=raw.get("country", ""),
                    locations_text=", ".join(all_locations),
                ),
                content=JobContent(
                    description_html=raw.get("description", ""),
                    description_plain=raw.get("descriptionPlain", ""),
                ),
                compensation=JobCompensation(
                    salary_min=raw.get("salaryRange", {}).get("min"),
                    salary_max=raw.get("salaryRange", {}).get("max"),
                    salary_currency=raw.get("salaryRange", {}).get("currency", ""),
                    salary_period=raw.get("salaryRange", {}).get("interval", ""),
                    salary_description=raw.get("salaryDescriptionPlain", ""),
                ),
                dates=JobDates(
                    posted_on=Normalizer._ts_to_date(raw.get("created_at")),
                ),
                language=Normalizer._detect_language(raw.get("text", "")),
            )
        except Exception:
            return None

    @staticmethod
    def normalize_workday(raw: dict, config) -> Optional[Job]:
        try:
            return Job(
                source=JobSource(
                    type=SourceType.WORKDAY,
                    company_name=config.name,
                    company_name_cn=config.name_cn,
                    source_url=raw.get("externalUrl", ""),
                    external_id=raw.get("externalPath", ""),
                    fetched_at=datetime.now(CST).isoformat(),
                ),
                job=JobInfo(
                    title=raw.get("title", ""),
                    employment_type=Normalizer._infer_employment_type(raw.get("timeType", "")),
                ),
                location=JobLocation(
                    city=raw.get("location", ""),
                    locations_text=raw.get("locationsText", ""),
                ),
                content=JobContent(
                    description_html=raw.get("jobDescription", ""),
                    description_plain=Normalizer._strip_html(raw.get("jobDescription", "")),
                ),
                dates=JobDates(
                    posted_on=raw.get("postedOn", "")[:10] if raw.get("postedOn") else "",
                ),
            )
        except Exception:
            return None

    @staticmethod
    def normalize_manual(raw: dict, config) -> Optional[Job]:
        return Job(
            source=JobSource(
                type=SourceType.MANUAL,
                company_name=raw.get("company_name", config.name),
                company_name_cn=raw.get("company_name_cn", config.name_cn),
                source_url=raw.get("source_url", ""),
                external_id=raw.get("external_id", ""),
                fetched_at=datetime.now(CST).isoformat(),
            ),
            job=JobInfo(
                title=raw.get("title", ""),
                title_cn=raw.get("title_cn", ""),
                department=raw.get("department", ""),
                team=raw.get("team", ""),
                employment_type=Normalizer._infer_employment_type(raw.get("employment_type", "")),
                workplace_type=Normalizer._parse_workplace_type(raw.get("workplace_type", "unspecified")),
            ),
            location=JobLocation(
                city=raw.get("city", ""),
                province=raw.get("province", ""),
                country=raw.get("country", ""),
                locations_text=raw.get("locations_text", ""),
            ),
            content=JobContent(
                description_plain=raw.get("description_plain", ""),
                description_html=raw.get("description_html", ""),
                responsibilities=raw.get("responsibilities", []),
                qualifications=raw.get("qualifications", []),
            ),
            compensation=JobCompensation(
                salary_min=raw.get("salary_min"),
                salary_max=raw.get("salary_max"),
                salary_currency=raw.get("salary_currency", ""),
                salary_period=raw.get("salary_period", ""),
                salary_description=raw.get("salary_description", ""),
            ),
            dates=JobDates(
                posted_on=raw.get("posted_on", ""),
                closing_on=raw.get("closing_on", ""),
            ),
            language=raw.get("language", "zh"),
        )

    # === helpers ===

    @staticmethod
    def _strip_html(html: str) -> str:
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ").strip()
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _ts_to_date(ts) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromtimestamp(ts / 1000, tz=CST).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text:
            return "en"
        cjk_count = len(re.findall(r"[一-鿿]", text))
        return "zh" if cjk_count > len(text) * 0.3 else "en"

    @staticmethod
    def _infer_workplace_type(locations: list[str]) -> WorkplaceType:
        text = " ".join(locations).lower()
        if "remote" in text:
            return WorkplaceType.REMOTE
        if "hybrid" in text:
            return WorkplaceType.HYBRID
        return WorkplaceType.ON_SITE

    @staticmethod
    def _parse_workplace_type(raw: str) -> WorkplaceType:
        mapping = {
            "remote": WorkplaceType.REMOTE,
            "hybrid": WorkplaceType.HYBRID,
            "on-site": WorkplaceType.ON_SITE,
            "on_site": WorkplaceType.ON_SITE,
        }
        return mapping.get(raw.lower(), WorkplaceType.UNSPECIFIED)

    @staticmethod
    def _infer_employment_type(text: str) -> EmploymentType:
        t = text.lower()
        if "intern" in t or "实习" in t:
            return EmploymentType.INTERN
        if "contract" in t or "合同" in t:
            return EmploymentType.CONTRACT
        if "part" in t or "兼职" in t:
            return EmploymentType.PART_TIME
        if "full" in t or "全职" in t:
            return EmploymentType.FULL_TIME
        return EmploymentType.UNSPECIFIED

    @staticmethod
    def _infer_country(locations: list[str]) -> str:
        text = " ".join(locations)
        for city in ["Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Hangzhou", "Chengdu", "China", "北京", "上海", "深圳"]:
            if city in text:
                return "CN"
        return ""
