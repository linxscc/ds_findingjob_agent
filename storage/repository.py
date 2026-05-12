"""数据访问层：Job CRUD"""

import json
import logging
from datetime import datetime

from storage.database import Database
from models.job import Job

logger = logging.getLogger(__name__)

INSERT_SQL = """
INSERT INTO jobs (id, external_id, source_type, company_name, company_name_cn,
    source_url, fetched_at, is_active, title, title_cn, department, team_name,
    employment_type, workplace_type, seniority_level, city, province, country,
    is_remote_cn, locations_text, description_plain, description_html,
    responsibilities, qualifications, salary_min, salary_max, salary_currency,
    salary_period, salary_desc, posted_on, closing_on, is_software_role,
    matched_keywords, match_score, match_level, language, raw_json)
VALUES (%(id)s, %(external_id)s, %(source_type)s, %(company_name)s, %(company_name_cn)s,
    %(source_url)s, %(fetched_at)s, %(is_active)s, %(title)s, %(title_cn)s,
    %(department)s, %(team_name)s, %(employment_type)s, %(workplace_type)s,
    %(seniority_level)s, %(city)s, %(province)s, %(country)s,
    %(is_remote_cn)s, %(locations_text)s, %(description_plain)s,
    %(description_html)s, %(responsibilities)s, %(qualifications)s,
    %(salary_min)s, %(salary_max)s, %(salary_currency)s,
    %(salary_period)s, %(salary_desc)s, %(posted_on)s, %(closing_on)s,
    %(is_software_role)s, %(matched_keywords)s, %(match_score)s,
    %(match_level)s, %(language)s, %(raw_json)s)
ON DUPLICATE KEY UPDATE
    is_active = VALUES(is_active),
    title = VALUES(title),
    locations_text = VALUES(locations_text),
    updated_at = CURRENT_TIMESTAMP
"""


class JobRepository:
    def __init__(self, db: Database):
        self.db = db

    def save(self, job: Job):
        params = {
            "id": job.id,
            "external_id": job.source.external_id,
            "source_type": job.source.type.value,
            "company_name": job.source.company_name,
            "company_name_cn": job.source.company_name_cn,
            "source_url": job.source.source_url[:1024],
            "fetched_at": job.source.fetched_at,
            "is_active": 1 if job.source.is_active else 0,
            "title": job.job.title[:512],
            "title_cn": job.job.title_cn[:512],
            "department": job.job.department,
            "team_name": job.job.team,
            "employment_type": job.job.employment_type.value,
            "workplace_type": job.job.workplace_type.value,
            "seniority_level": job.job.seniority_level,
            "city": job.location.city,
            "province": job.location.province,
            "country": job.location.country,
            "is_remote_cn": 1 if job.location.is_remote_in_china else 0,
            "locations_text": job.location.locations_text,
            "description_plain": job.content.description_plain,
            "description_html": job.content.description_html,
            "responsibilities": json.dumps(job.content.responsibilities, ensure_ascii=False),
            "qualifications": json.dumps(job.content.qualifications, ensure_ascii=False),
            "salary_min": job.compensation.salary_min,
            "salary_max": job.compensation.salary_max,
            "salary_currency": job.compensation.salary_currency,
            "salary_period": job.compensation.salary_period,
            "salary_desc": job.compensation.salary_description,
            "posted_on": job.dates.posted_on or None,
            "closing_on": job.dates.closing_on or None,
            "is_software_role": 1 if job.filter_result.is_software_role else 0,
            "matched_keywords": json.dumps(job.filter_result.matched_keywords, ensure_ascii=False),
            "match_score": job.filter_result.match_score,
            "match_level": job.filter_result.match_level.value,
            "language": job.language,
            "raw_json": json.dumps(job.to_dict(), ensure_ascii=False),
        }
        try:
            self.db.execute(INSERT_SQL, params)
        except Exception as e:
            logger.error(f"Failed to save job {job.id}: {e}")

    def save_many(self, jobs: list[Job]):
        for job in jobs:
            self.save(job)

    def query_software_jobs(self, match_level: str = "strong") -> list[dict]:
        sql = "SELECT * FROM jobs WHERE is_software_role = 1 AND is_active = 1"
        if match_level:
            sql += f" AND match_level = '{match_level}'"
        sql += " ORDER BY posted_on DESC"
        return self.db.execute(sql)

    def mark_inactive(self, job_id: str):
        self.db.execute("UPDATE jobs SET is_active = 0 WHERE id = %s", (job_id,))
