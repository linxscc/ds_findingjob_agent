import hashlib
import re

from models.job import Job


class Deduplicator:
    def __init__(self):
        self._seen: set[str] = set()

    def is_duplicate(self, job: Job) -> bool:
        """三重去重：URL + external_id + content_hash"""
        keys = [
            job.source.source_url,
            f"{job.source.company_name}:{job.source.external_id}",
            self._content_hash(job),
        ]
        for key in keys:
            if key and key in self._seen:
                return True
        for key in keys:
            if key:
                self._seen.add(key)
        return False

    def clear(self):
        self._seen.clear()

    @staticmethod
    def _content_hash(job: Job) -> str:
        text = f"{job.job.title}|{job.location.locations_text}|{job.content.description_plain[:200]}"
        text = re.sub(r"\s+", " ", text).strip().lower()
        return hashlib.md5(text.encode("utf-8")).hexdigest()
