"""半自动导入：用户粘贴微信/小程序文本，LLM 解析为结构化数据"""

import json
import logging

from core.collector import Collector
from core.normalizer import Normalizer
from models.job import Job

logger = logging.getLogger(__name__)


class ManualImportCollector(Collector):
    """接受粘贴文本 → LLM 解析 → 返回结构化 Job"""

    SYSTEM_PROMPT = """你是一个招聘信息解析助手。用户会粘贴一段招聘文本（来自微信公众号、小程序等）。
请从文本中提取以下字段，返回严格的 JSON 格式（不要 markdown 标记）：

{
  "company_name": "公司英文名",
  "company_name_cn": "公司中文名",
  "title": "岗位名称（英文或原文）",
  "title_cn": "岗位名称（中文翻译，如有）",
  "department": "部门",
  "team": "团队",
  "city": "工作城市",
  "province": "省份",
  "country": "国家代码（CN/US等）",
  "employment_type": "full_time/part_time/contract/intern",
  "workplace_type": "on_site/remote/hybrid",
  "salary_min": 数字或null,
  "salary_max": 数字或null,
  "salary_currency": "CNY/USD等",
  "salary_period": "annual/monthly",
  "description_plain": "岗位描述纯文本",
  "responsibilities": ["职责1", "职责2"],
  "qualifications": ["要求1", "要求2"],
  "posted_on": "发布日期 YYYY-MM-DD",
  "language": "zh/en/bilingual"
}

只返回 JSON，不要任何解释。"""

    def __init__(self, config, llm_client=None):
        super().__init__(config)
        self.llm_client = llm_client

    def fetch(self) -> list[Job]:
        logger.warning("ManualImportCollector.fetch() needs user input. Use parse_text() instead.")
        return []

    def parse_text(self, text: str) -> Job | None:
        """调用 LLM 解析粘贴文本"""
        if self.llm_client is None:
            return self._parse_fallback(text)

        try:
            response = self.llm_client.messages.create(
                model=self.llm_client.model,
                max_tokens=2000,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": text}],
            )
            raw_json = response.content[0].text.strip()
            if raw_json.startswith("```"):
                raw_json = raw_json.split("```")[1]
                if raw_json.startswith("json"):
                    raw_json = raw_json[5:]
            parsed = json.loads(raw_json)
            return Normalizer.normalize_manual(parsed, self.config)
        except Exception as e:
            logger.error(f"LLM parse failed: {e}")
            return self._parse_fallback(text)

    def _parse_fallback(self, text: str) -> Job | None:
        """无 LLM 时的退化方案：最小化解析"""
        return Normalizer.normalize_manual({
            "description_plain": text,
            "language": "zh" if any("一" <= c <= "鿿" for c in text[:100]) else "en",
        }, self.config)
