"""DS FindingJob Agent - 外企软件开发岗位采集"""

import argparse
import logging
import uuid
import yaml
from datetime import datetime
from pathlib import Path

from models.enums import SourceType
from models.source import SourceConfig
from core.rate_limiter import RateLimiter
from core.filter import JobFilter
from core.dedup import Deduplicator

from sources.ats_greenhouse import GreenhouseCollector
from sources.ats_lever import LeverCollector
from sources.ats_workday import WorkdayCollector
from sources.web_generic import GenericWebCollector
from sources.web_playwright import PlaywrightCollector
from sources.manual_import import ManualImportCollector
from sources.discovery import discover_foreign_companies, check_ats_endpoint

from storage.database import Database
from storage.repository import JobRepository
from storage.export import export_json, export_excel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

BASE_DIR = Path(__file__).parent


def load_yaml(name: str) -> dict:
    with open(BASE_DIR / "config" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    return load_yaml("settings.yaml")


def load_keywords() -> dict:
    return load_yaml("keywords.yaml")


def load_companies() -> list[SourceConfig]:
    data = load_yaml("companies.yaml")
    configs = []
    for c in data["companies"]:
        if not c.get("enabled", True):
            continue
        configs.append(SourceConfig(
            name=c["name"],
            name_cn=c.get("name_cn", ""),
            type=SourceType(c["type"]),
            url=c["url"],
            china_locations=c.get("china_locations", []),
            board_token=c.get("board_token"),
            site=c.get("site"),
            tenant=c.get("tenant"),
            wd_server=c.get("wd_server"),
            selectors=c.get("selectors"),
        ))
    return configs


def load_chinese_companies() -> list[str]:
    """加载中国本土公司排除列表"""
    data = load_yaml("chinese_companies.yaml")
    return data.get("chinese_companies", [])


def build_collector(config: SourceConfig, rate_limiter: RateLimiter, settings: dict):
    t = config.type
    if t == SourceType.GREENHOUSE:
        return GreenhouseCollector(config, rate_limiter)
    elif t == SourceType.LEVER:
        return LeverCollector(config, rate_limiter)
    elif t == SourceType.WORKDAY:
        return WorkdayCollector(config, rate_limiter)
    elif t == SourceType.GENERIC_WEB:
        pw_cfg = settings.get("playwright", {})
        return PlaywrightCollector(
            config, rate_limiter,
            headless=pw_cfg.get("headless", True),
            wait_until=pw_cfg.get("wait_until", "networkidle"),
        )
    else:
        raise ValueError(f"Unknown source type: {t}")


def cmd_collect(args):
    settings = load_settings()
    keywords = load_keywords()
    companies = load_companies()
    chinese_companies = load_chinese_companies()

    rate_limiter = RateLimiter(settings["collector"]["request_interval"])
    job_filter = JobFilter(
        title_keywords=keywords["title_keywords"],
        skill_keywords=keywords["skill_keywords"],
        china_only=settings["filter"]["china_only"],
        allow_remote_china=settings["filter"]["allow_remote_china"],
        chinese_companies=chinese_companies,
    )
    dedup = Deduplicator()

    # 统计
    stats = {
        "total_fetched": 0,
        "filtered_chinese_co": 0,
        "filtered_not_china": 0,
        "filtered_not_software": 0,
        "filtered_dup": 0,
        "saved": 0,
        "errors": 0,
    }
    software_jobs = []

    for cfg in companies:
        logger.info(f"Fetching: {cfg.name} ({cfg.type.value})")
        try:
            collector = build_collector(cfg, rate_limiter, settings)
            raw_jobs = collector.fetch()
            stats["total_fetched"] += len(raw_jobs)
            logger.info(f"  Fetched {len(raw_jobs)} jobs")
        except Exception as e:
            logger.error(f"  Failed: {cfg.name}: {e}")
            stats["errors"] += 1
            continue

        for job in raw_jobs:
            job.id = str(uuid.uuid4())

            # 第一道：地点过滤（只保留中国境内或允许中国远程的）
            if not job_filter.should_process(job):
                stats["filtered_not_china"] += 1
                continue

            # 第二道：排除中国本土公司
            if job_filter.is_chinese_company(job.source.company_name):
                stats["filtered_chinese_co"] += 1
                continue

            # 第三道：去重
            if dedup.is_duplicate(job):
                stats["filtered_dup"] += 1
                continue

            # 第四道：软件岗位关键词匹配
            job.filter_result = job_filter.evaluate(job)
            if not job.filter_result.is_software_role:
                stats["filtered_not_software"] += 1
                continue

            software_jobs.append(job)
            stats["saved"] += 1

    # 按匹配度排序
    software_jobs.sort(key=lambda j: j.filter_result.match_score, reverse=True)

    logger.info("=" * 60)
    logger.info(f"Collect Summary")
    logger.info(f"  Total fetched:      {stats['total_fetched']}")
    logger.info(f"  Not China:          {stats['filtered_not_china']}")
    logger.info(f"  Chinese company:    {stats['filtered_chinese_co']}")
    logger.info(f"  Duplicates:         {stats['filtered_dup']}")
    logger.info(f"  Not software:       {stats['filtered_not_software']}")
    logger.info(f"  Errors:             {stats['errors']}")
    logger.info(f"  SAVED (software):   {stats['saved']}")
    logger.info(f"  - Strong match:     {sum(1 for j in software_jobs if j.filter_result.match_level.value == 'strong')}")
    logger.info(f"  - Partial match:    {sum(1 for j in software_jobs if j.filter_result.match_level.value == 'partial')}")
    logger.info("=" * 60)

    if not software_jobs:
        logger.warning("No software jobs found. Check companies.yaml URLs and network.")
        return

    # Save to DB
    db_cfg = settings.get("database", {})
    if db_cfg.get("password"):
        try:
            db = Database(**db_cfg)
            db.connect()
            db.ensure_schema()
            repo = JobRepository(db)
            repo.save_many(software_jobs)
            logger.info(f"Saved to MySQL: {db_cfg['host']}/{db_cfg['database']}")
            db.close()
        except Exception as e:
            logger.error(f"Database error: {e}")

    # Export
    export_cfg = settings.get("export", {})
    output_dir = export_cfg.get("output_dir", "./output")
    fmt = args.format or export_cfg.get("default_format", "json")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    export_data = [j.to_dict() for j in software_jobs]

    if fmt == "json":
        export_json(export_data, f"{output_dir}/jobs_{timestamp}.json")
    elif fmt == "excel":
        flat = []
        for j in export_data:
            row = {}
            row.update(j["source"])
            row.update(j["job"])
            row.update(j["location"])
            row.update(j["content"])
            row.update(j["compensation"])
            row.update(j["dates"])
            row.update(j["filter_result"])
            row["language"] = j["language"]
            row["id"] = j["id"]
            flat.append(row)
        export_excel(flat, f"{output_dir}/jobs_{timestamp}.xlsx")


def cmd_discover(args):
    """从招聘平台发现外企并自动检测 ATS（主动探测 + 可选猎聘抓取）"""
    settings = load_settings()
    chinese_companies = load_chinese_companies()
    chinese_set = {c.lower() for c in chinese_companies}

    pw_cfg = settings.get("playwright", {})
    pw_config = {
        "headless": not args.no_headless,
        "timeout": pw_cfg.get("timeout", 30000),
    }

    logger.info("Starting discovery...")
    discovered = discover_foreign_companies(pw_config, include_scraping=args.scrape)

    if not discovered:
        logger.warning("No companies discovered. Check network/Playwright installation.")
        return

    logger.info(f"Total discovered: {len(discovered)} companies")

    # 处理发现结果
    ats_found = []   # 已有 ATS 信息（来自 Phase 2 探测）
    need_check = []  # 需要检查 ATS（来自 Phase 1 猎聘）
    chinese_filtered = 0

    for c in discovered:
        name = c["name"]

        # 排除中国本土公司
        name_lower = name.lower()
        if any(cc in name_lower or name_lower in cc for cc in chinese_set):
            chinese_filtered += 1
            continue

        if "type" in c:
            # 来自 Phase 2 探测，已有 ATS 信息
            logger.info(f"  {name}: {c['type']} ({c.get('job_count', '?')} jobs)")
            ats_found.append(c)
        else:
            need_check.append(c)

    # 对 Phase 1 猎聘发现的公司，检测 ATS 端点
    for c in need_check:
        name = c["name"]
        logger.info(f"  Checking ATS: {name} ...")
        endpoint = check_ats_endpoint(name)
        if endpoint:
            logger.info(f"    -> {endpoint['type']}: {endpoint['url']} ({endpoint['job_count']} jobs)")
            ats_found.append({**c, **endpoint})
        else:
            # 尝试用公司英文名再做一次探测
            # 很多猎聘上的外企显示的是中文名，尝试用拼音/简写
            logger.info(f"    -> No ATS found")

    # 输出结果
    no_ats = [c for c in need_check if "type" not in c]

    logger.info("=" * 60)
    logger.info(f"Discovery Summary")
    logger.info(f"  Total found:        {len(discovered)}")
    logger.info(f"  Chinese filtered:   {chinese_filtered}")
    logger.info(f"  ATS identified:     {len(ats_found)}")
    logger.info(f"  No ATS:             {len(no_ats)}")
    logger.info("=" * 60)

    if ats_found:
        logger.info("ATS-identified companies (ready for companies.yaml):")
        for r in ats_found:
            print(f"\n  - name: \"{r['name']}\"")
            print(f"    type: {r['type']}")
            if r['type'] == 'greenhouse':
                print(f"    board_token: \"{r['board_token']}\"")
            elif r['type'] == 'lever':
                print(f"    site: \"{r['site']}\"")
            print(f"    url: \"{r['url']}\"")
            print(f"    china_locations: [\"China\", \"Remote\"]")

    if no_ats:
        logger.info("Companies without detected ATS (need manual investigation):")
        for r in no_ats:
            print(f"  - {r['name']} (source: {r.get('source', '?')})")


def cmd_manual(args):
    """半自动导入：从文本文件或 stdin 粘贴招聘信息"""
    settings = load_settings()
    keywords = load_keywords()
    job_filter = JobFilter(
        title_keywords=keywords["title_keywords"],
        skill_keywords=keywords["skill_keywords"],
        china_only=False,
    )

    config = SourceConfig(name="manual", name_cn="手动导入", type=SourceType.MANUAL, url="")
    collector = ManualImportCollector(config)

    text = ""
    if args.file:
        text = open(args.file, encoding="utf-8").read()
    else:
        print("粘贴招聘文本（输入 END 结束）：")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        text = "\n".join(lines)

    if not text.strip():
        logger.error("No text provided")
        return

    job = collector.parse_text(text)
    if job is None:
        logger.error("Failed to parse text")
        return

    job.id = str(uuid.uuid4())
    job.filter_result = job_filter.evaluate(job)

    export_data = [job.to_dict()]
    export_cfg = settings.get("export", {})
    output_dir = export_cfg.get("output_dir", "./output")
    export_json(export_data, f"{output_dir}/manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    logger.info(f"Parsed: {job.job.title} @ {job.location.city} [{job.filter_result.match_level.value}]")


def main():
    parser = argparse.ArgumentParser(description="DS FindingJob Agent")
    sub = parser.add_subparsers(dest="command")

    collect = sub.add_parser("collect", help="从所有启用的数据源采集岗位")
    collect.add_argument("-f", "--format", choices=["json", "excel"], help="输出格式")

    discover = sub.add_parser("discover", help="从招聘平台发现外企并检测 ATS")
    discover.add_argument("--scrape", action="store_true", help="同时从猎聘抓取（可能触发验证码）")
    discover.add_argument("--no-headless", action="store_true", help="猎聘抓取时显示浏览器窗口")

    manual = sub.add_parser("manual", help="手动粘贴招聘文本导入")
    manual.add_argument("-f", "--file", help="从文件读取招聘文本")

    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "manual":
        cmd_manual(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
