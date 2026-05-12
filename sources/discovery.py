"""发现模块：自动发现使用 Greenhouse/Lever 的外企

策略（按可靠性排序）：
  1. 主动探测常见外企的 Greenhouse/Lever API（可靠，无反爬）
  2. 猎聘 API 拦截（可能触发 CAPTCHA，需要干净 IP）
  3. BOSS/51job 不可用（反爬严格）

使用方式：
  discover 命令 → Phase 1 主动探测 + Phase 2 猎聘抓取（可选）
"""

import logging
import re
import time

logger = logging.getLogger(__name__)

# =========================================================================
# Phase 1: 主动探测已知外企的 ATS 端点
# =========================================================================

# 候选外企（不在 companies.yaml 中，可能在中国有岗位）
PROBE_CANDIDATES = [
    # 游戏公司
    "Electronic Arts", "EA", "Ubisoft", "Take-Two", "Nintendo",
    "Square Enix", "Capcom", "Bandai Namco", "Sega", "Activision",
    "Blizzard", "Krafton", "NCSoft", "Nexon", "Pearl Abyss",
    "Wargaming", "DeNA", "GREE", "GungHo", "Cygames",
    "Gameloft", "Rovio", "Supercell", "King", "Zynga",
    "Playrix", "Playtika", "Scopely", "Niantic",

    # SaaS / 企业软件
    "Salesforce", "Servicenow", "Workday", "Autodesk", "Adobe",
    "SAP", "Oracle", "Intuit", "HubSpot", "Zendesk",
    "Splunk", "New Relic", "Dynatrace", "Palantir", "Crowdstrike",
    "Zscaler", "Palo Alto Networks", "Fortinet", "Citrix",
    "VMware", "Nutanix", "Pure Storage", "NetApp",
    "Freshworks", "Atlassian", "Miro", "Mural", "Coda",
    "Airtable", "Asana", "Monday.com", "Wrike", "Smartsheet",
    "DocuSign", "Box", "Dropbox", "Slack",

    # 互联网 / 消费科技
    "Spotify", "Netflix", "Snap", "Uber", "DoorDash",
    "Yelp", "Etsy", "Wayfair", "Chewy", "Expedia",
    "TripAdvisor", "Agoda", "Booking.com", "Skyscanner",
    "Zillow", "Opendoor", "Carvana", "Instacart", "Deliveroo",
    "Grab", "Gojek", "Razer", "Shopback",

    # 半导体 / 硬件
    "AMD", "Intel", "Qualcomm", "Micron", "Texas Instruments",
    "Analog Devices", "NXP", "Infineon", "ARM", "MediaTek",
    "Broadcom", "ASML", "Lam Research", "Applied Materials",
    "NVIDIA", "AMD", "Marvell", "Synaptics", "Cadence",
    "Synopsys", "Ansys", "Autodesk",

    # 金融科技 / 支付
    "PayPal", "Square", "Adyen", "Revolut", "Wise",
    "Coinbase", "Robinhood", "Plaid", "Stripe",
    "Checkout.com", "Rapyd", "Marqeta", "Affirm",
    "Klarna", "Afterpay", "Chime", "Nubank",

    # 工业 / 制造
    "Siemens", "Bosch", "Schneider Electric", "ABB",
    "Rockwell", "Emerson", "Honeywell", "General Electric",
    "Philips", "Thermo Fisher", "Danaher", "Agilent",
    "Caterpillar", "John Deere", "Cummins",

    # 汽车 / 出行
    "Tesla", "Rivian", "Lucid", "Waymo", "Cruise",
    "Aurora", "Zoox", "Nuro", "Mobileye",
    "BMW", "Mercedes-Benz", "Volkswagen", "Volvo",
    "Ford", "General Motors", "Stellantis",

    # 消费品 / 零售
    "Nike", "Adidas", "Unilever", "P&G", "LVMH",
    "L'Oreal", "Estee Lauder", "Coca-Cola", "PepsiCo",
    "Starbucks", "McDonald's", "IKEA",

    # 医疗
    "Johnson & Johnson", "Pfizer", "Roche", "Novartis",
    "Merck", "AstraZeneca", "Sanofi", "GSK",
    "Medtronic", "Boston Scientific", "Stryker",
]


def probe_ats_endpoints(candidates: list[str] = None) -> list[dict]:
    """主动探测候选公司列表的 Greenhouse/Lever 端点

    返回已确认存在 ATS 的公司列表
    """
    import requests

    if candidates is None:
        candidates = PROBE_CANDIDATES

    results = []
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    session.headers.update(headers)

    for name in candidates:
        name_lower = name.lower().strip()
        # 生成候选 token/site 名
        tokens = [
            name_lower.replace(" ", ""),
            name_lower.replace(" ", "-"),
            name_lower.replace(" ", "").replace(".", "").replace("&", ""),
            re.sub(r"[^a-z0-9]", "", name_lower),
        ]
        # 去掉常见后缀再试
        for suffix in ["inc", "corp", "corporation", "ltd", "limited", "llc", "plc", "gmbh"]:
            clean = name_lower.replace(f" {suffix}", "").replace(suffix, "")
            if clean != name_lower:
                tokens.append(clean.replace(" ", ""))
                tokens.append(clean.replace(" ", "-"))

        tokens = list(dict.fromkeys([t for t in tokens if t]))

        found = None
        # Greenhouse
        for token in tokens:
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
            try:
                r = session.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    total = data.get('meta', {}).get('total', 0)
                    if total > 0:
                        found = {"type": "greenhouse", "board_token": token,
                                 "job_count": total,
                                 "url": f"https://boards.greenhouse.io/{token}"}
                        break
            except Exception:
                continue

        # Lever
        if not found:
            for site in tokens:
                url = f"https://api.lever.co/v0/postings/{site}?mode=json"
                try:
                    r = session.get(url, timeout=10)
                    if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
                        found = {"type": "lever", "site": site,
                                 "job_count": len(r.json()),
                                 "url": f"https://jobs.lever.co/{site}"}
                        break
                except Exception:
                    continue

        if found:
            logger.info(f"  {name}: {found['type']} ({found['job_count']} jobs)")
            results.append({"name": name, **found, "source": "probe"})

    return results


# =========================================================================
# Phase 2: 猎聘 API 拦截（可选，可能触发 CAPTCHA）
# =========================================================================

# 猎头公司关键词
HEADHUNTER_KEYWORDS = [
    "michael page", "robert walters", "hays", "randstad",
    "manpower", "adecco", "kelly services", "robert half",
    "morgan mckinley", "spring professional", "connectedgroup",
    "links international", "bo le", "boyden", "egon zehnder",
    "heidrick", "korn ferry", "russell reynolds", "spencer stuart",
    "pagegroup", "page personnel", "allegis", "teksystems",
    "experis", "career international",
    "米高蒲志", "华德士", "瀚纳仕", "任仕达", "万宝盛华", "德科",
    "michael page", "robert half",
]


def discover_from_liepin(playwright_config: dict = None) -> list[dict]:
    """猎聘：Playwright 加载页面，拦截内部搜索 API 的 JSON 响应

    注意：可能触发 IP CAPTCHA。如果被拦截，请稍后再试或使用非 headless 模式。
    """
    pw_cfg = playwright_config or {}
    headless = pw_cfg.get("headless", True)
    timeout = pw_cfg.get("timeout", 30000)
    companies = {}
    headhunter_lower = [h.lower() for h in HEADHUNTER_KEYWORDS]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        search_queries = ["外企", "外企 软件", "foreign company"]
        all_urls = []

        page = context.new_page()

        # 监听所有导航，检测 CAPTCHA
        def log_navigation(frame):
            url = frame.url
            all_urls.append(url)
            if 'captcha' in url.lower() or 'safe.liepin.com' in url:
                logger.warning(f"  CAPTCHA detected: {url[:100]}...")

        page.on('framenavigated', log_navigation)

        for query in search_queries:
            captured = []

            def make_handler(capture_list):
                def handle_response(response):
                    if 'pc-search-job' in response.url and 'api-c.liepin.com' in response.url:
                        try:
                            body = response.json()
                            job_list = body.get('data', {}).get('data', {}).get('jobCardList', [])
                            capture_list.extend(job_list)
                        except Exception:
                            pass
                return handle_response

            page.on('response', make_handler(captured))

            for dq_code in ["020", "010", "000"]:
                try:
                    url = f"https://www.liepin.com/zhaopin/?key={query}&dqs={dq_code}"
                    page.goto(url, wait_until="networkidle", timeout=timeout)
                    time.sleep(3)

                    # 检测是否被 CAPTCHA 拦截
                    if 'captcha' in page.url.lower() or 'safe.liepin.com' in page.url:
                        logger.warning(f"  CAPTCHA page detected for query '{query}', stopping Liepin scraping")
                        break

                except Exception as e:
                    logger.warning(f"  Navigation failed: {e}")
                    continue

            for job in captured:
                comp = job.get('comp', {})
                job_info = job.get('job', {})
                company_name = comp.get('compName', '').strip()

                if not company_name or len(company_name) < 2:
                    continue
                if company_name in companies:
                    continue

                name_lower = company_name.lower()
                if any(hh in name_lower for hh in headhunter_lower):
                    continue

                companies[company_name] = {
                    "name": company_name,
                    "industry": comp.get('compIndustry', ''),
                    "sample_title": job_info.get('title', ''),
                    "sample_location": job_info.get('dq', ''),
                    "source": "Liepin",
                }

            logger.info(f"  Liepin '{query}': {len(captured)} jobs, {len(companies)} unique companies")

        page.close()
        browser.close()

    return list(companies.values())


# =========================================================================
# ATS 端点检测
# =========================================================================

def check_ats_endpoint(company_name: str) -> dict | None:
    """检测单个公司使用的 ATS 平台（Greenhouse / Lever）"""
    import requests

    name_lower = company_name.lower().strip()
    for suffix in [" inc", " corp", " ltd", " limited", " co.", " co", " llc", " plc", " gmbh", " s.a.", " b.v."]:
        name_lower = name_lower.replace(suffix, "")

    candidates = [
        name_lower.replace(" ", ""),
        name_lower.replace(" ", "-"),
        re.sub(r"[^a-z0-9]", "", name_lower),
    ]
    candidates = list(dict.fromkeys([c for c in candidates if c]))

    headers = {"User-Agent": "Mozilla/5.0"}

    for token in candidates:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        try:
            r = requests.get(url, timeout=10, headers=headers)
            if r.status_code == 200 and r.json().get("meta", {}).get("total", 0) > 0:
                return {"type": "greenhouse", "board_token": token,
                        "job_count": r.json()["meta"]["total"],
                        "url": f"https://boards.greenhouse.io/{token}"}
        except Exception:
            continue

    for site in candidates:
        url = f"https://api.lever.co/v0/postings/{site}?mode=json"
        try:
            r = requests.get(url, timeout=10, headers=headers)
            if r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0:
                return {"type": "lever", "site": site,
                        "job_count": len(r.json()),
                        "url": f"https://jobs.lever.co/{site}"}
        except Exception:
            continue

    return None


# =========================================================================
# 主入口
# =========================================================================

def discover_foreign_companies(playwright_config: dict = None, include_scraping: bool = False) -> list[dict]:
    """发现外企：主动探测 + 可选猎聘抓取

    Args:
        playwright_config: Playwright 配置 (headless, timeout)
        include_scraping: 是否包含猎聘抓取（可能触发 CAPTCHA）
    """
    all_companies = []

    # Phase 1: 主动探测（可靠，无反爬风险）
    logger.info("Phase 1: Probing known foreign companies on Greenhouse/Lever...")
    try:
        probe_results = probe_ats_endpoints()
        all_companies.extend(probe_results)
        logger.info(f"  Probe found: {len(probe_results)} companies with ATS")
    except Exception as e:
        logger.error(f"  Probe failed: {e}")

    # Phase 2: 猎聘抓取（可选，可能触发 CAPTCHA）
    if include_scraping:
        logger.info("Phase 2: Scraping Liepin (may trigger CAPTCHA)...")
        try:
            liepin_results = discover_from_liepin(playwright_config)
            # 去重
            existing = {c['name'].lower() for c in all_companies}
            new_count = 0
            for r in liepin_results:
                if r['name'].lower() not in existing:
                    all_companies.append(r)
                    new_count += 1
            logger.info(f"  Liepin found: {len(liepin_results)} companies ({new_count} new)")
        except Exception as e:
            logger.error(f"  Liepin failed: {e}")

    return all_companies
