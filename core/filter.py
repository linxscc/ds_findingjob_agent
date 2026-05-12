import re
import logging

from models.enums import MatchLevel
from models.job import Job, FilterResult

logger = logging.getLogger(__name__)

# 中国城市（中英文）
CHINA_CITIES = [
    "beijing", "shanghai", "shenzhen", "guangzhou", "hangzhou", "chengdu",
    "nanjing", "wuhan", "suzhou", "xian", "tianjin", "chongqing", "dalian",
    "qingdao", "xiamen", "hefei", "changsha", "ningbo", "fuzhou", "kunming",
    "shenyang", "wuxi", "jinan", "zhengzhou", "dongguan", "zhuhai",
    "北京", "上海", "深圳", "广州", "杭州", "成都", "南京", "武汉", "苏州",
    "西安", "天津", "重庆", "大连", "青岛", "厦门", "合肥", "长沙",
]

CHINA_COUNTRY_SIGNALS = ["china", "china mainland", "greater china", "cn", "中国"]


# 非开发岗位标题关键词（命中则直接排除，防止假阳性）
NON_SOFTWARE_TITLES = [
    # 销售/客户
    "account executive", "account manager", "sales", "business development",
    "territory account", "named account", "enterprise account",
    "客户经理", "销售", "业务拓展",
    # 人事/行政
    "recruiter", "talent", "human resources", "hr ", "people partner",
    "sourcer", "workplace", "executive assistant", "office manager",
    "receptionist", "facility", "人事", "招聘", "行政",
    # 市场/公关
    "marketing", "brand", "communications", "public relations",
    "content writer", "copywriter", "community manager",
    "市场", "公关", "文案",
    # 财务/法律
    "finance", "legal", "tax", "audit", "compliance officer",
    "accountant", "controller", "treasurer", "payroll",
    "investor", "venture", "财务", "法律", "审计",
    # 采购/供应链
    "procurement", "supply chain", "采购", "供应链",
    # 客服/支持（非技术）
    "customer success", "customer support", "customer service",
    "客服", "客户支持",
    # 非开发的游戏美术/设计/制作岗
    "game producer", "game designer", "level designer",
    "art director", "art project", "art manager",
    "animation artist", "3d artist", "visual design artist",
    "concept artist", "graphic designer", "motion designer",
    "technical artist", "character artist", "environment artist",
    "audio designer", "sound designer",
    "narrative designer", "content designer",
    "publishing product", "publishing manager",
    "游戏制作人", "游戏策划", "美术总监", "美术项目",
    "游戏美术", "3d美术", "动画师", "特效师",
    "video producer", "event producer",
    # 非技术总监/管理
    "director, insights", "director of insights",
    "workplace experience", "office experience",
    # 其他非开发职能
    "technical support engineer", "support engineer",
    "技术支持", "it support",
]


class JobFilter:
    def __init__(self, title_keywords: list[str], skill_keywords: list[str],
                 china_only: bool = True, allow_remote_china: bool = True,
                 chinese_companies: list[str] = None):
        self.title_keywords = [k.lower() for k in title_keywords]
        self.skill_keywords = [k.lower() for k in skill_keywords]
        self.exclude_titles = [k.lower() for k in NON_SOFTWARE_TITLES]
        self.chinese_companies = [c.lower() for c in (chinese_companies or [])]
        self.china_only = china_only
        self.allow_remote_china = allow_remote_china

    def is_chinese_company(self, company_name: str) -> bool:
        """检查是否为中国本土公司"""
        name_lower = company_name.lower()
        for cc in self.chinese_companies:
            if cc in name_lower or name_lower in cc:
                return True
        return False

    def should_process(self, job: Job) -> bool:
        """检查岗位是否在中国境内或允许中国远程"""
        if not self.china_only:
            return True

        loc_text = f"{job.location.city} {job.location.province} {job.location.country} {job.location.locations_text}".lower()

        has_china_city = any(city in loc_text for city in CHINA_CITIES)
        has_china_country = any(sig in loc_text for sig in CHINA_COUNTRY_SIGNALS)
        is_remote = "remote" in loc_text
        is_remote_china = self.allow_remote_china and is_remote and (has_china_city or has_china_country)

        return has_china_city or (has_china_country and not (is_remote and not self.allow_remote_china)) or is_remote_china

    def evaluate(self, job: Job) -> FilterResult:
        title_lower = job.job.title.lower()

        # 先检查排除词 — 标题命中非软件岗则直接排除
        for ex in self.exclude_titles:
            if ex in title_lower:
                return FilterResult(
                    is_software_role=False,
                    matched_keywords=[],
                    match_score=0.0,
                    match_level=MatchLevel.NONE,
                )

        desc_lower = f"{job.content.description_plain} {job.content.description_html}".lower()
        combined = f"{title_lower} {desc_lower}"

        matched = []
        score = 0.0

        # 标题关键词：标题短语匹配（子串即可，因为都是长短语）
        for kw in self.title_keywords:
            if kw in title_lower:
                matched.append(kw)
                score += 0.4

        # 技能关键词：整词匹配（避免 r/go/c 等短词误匹配）
        for kw in self.skill_keywords:
            if self._word_match(kw, combined):
                matched.append(kw)
                score += 0.2

        matched = list(dict.fromkeys(matched))
        score = min(score, 1.0)

        if score >= 0.6:
            level = MatchLevel.STRONG
        elif score >= 0.2:
            level = MatchLevel.PARTIAL
        else:
            level = MatchLevel.NONE

        return FilterResult(
            is_software_role=level != MatchLevel.NONE,
            matched_keywords=matched,
            match_score=round(score, 2),
            match_level=level,
        )

    @staticmethod
    def _word_match(keyword: str, text: str) -> bool:
        """整词匹配：对普通词用 \\b 边界，含特殊字符的词用子串"""
        # 含特殊字符的关键词（.net, c#, c++, node.js, ci/cd 等）用子串匹配
        if re.search(r"[.#+/]", keyword):
            return keyword in text
        # 普通词用整词边界匹配
        return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))
