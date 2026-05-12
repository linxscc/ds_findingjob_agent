"""导出：JSON / Excel"""

import json
import os
import logging

logger = logging.getLogger(__name__)


def export_json(jobs: list[dict], output_path: str):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    logger.info(f"Exported {len(jobs)} jobs to {output_path}")


def export_excel(jobs: list[dict], output_path: str):
    import pandas as pd

    df = pd.DataFrame(jobs)
    # Reorder and select key columns for readability
    columns = [
        "title", "company_name", "city", "country", "workplace_type",
        "employment_type", "department", "match_level", "match_score",
        "salary_min", "salary_max", "salary_currency", "salary_period",
        "posted_on", "source_url", "language",
    ]
    available = [c for c in columns if c in df.columns]
    remaining = [c for c in df.columns if c not in available]
    df = df[available + remaining]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")
    logger.info(f"Exported {len(jobs)} jobs to {output_path}")
