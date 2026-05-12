"""MySQL 连接管理与 DDL"""

import logging
import pymysql

logger = logging.getLogger(__name__)

DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              VARCHAR(36) PRIMARY KEY,
    external_id     VARCHAR(128) DEFAULT '',
    source_type     VARCHAR(32)  NOT NULL,
    company_name    VARCHAR(128) NOT NULL,
    company_name_cn VARCHAR(128) DEFAULT '',
    source_url      VARCHAR(1024) NOT NULL,
    fetched_at      DATETIME NOT NULL,
    is_active       TINYINT(1) DEFAULT 1,

    title           VARCHAR(512) NOT NULL,
    title_cn        VARCHAR(512) DEFAULT '',
    department      VARCHAR(256) DEFAULT '',
    team_name       VARCHAR(256) DEFAULT '',
    employment_type VARCHAR(32) DEFAULT '',
    workplace_type  VARCHAR(32) DEFAULT '',
    seniority_level VARCHAR(32) DEFAULT '',

    city            VARCHAR(128) DEFAULT '',
    province        VARCHAR(128) DEFAULT '',
    country         VARCHAR(8) DEFAULT '',
    is_remote_cn    TINYINT(1) DEFAULT 0,
    locations_text  VARCHAR(512) DEFAULT '',

    description_plain TEXT,
    description_html  MEDIUMTEXT,
    responsibilities  JSON,
    qualifications    JSON,

    salary_min        DOUBLE DEFAULT NULL,
    salary_max        DOUBLE DEFAULT NULL,
    salary_currency   VARCHAR(8) DEFAULT '',
    salary_period     VARCHAR(16) DEFAULT '',
    salary_desc       TEXT,

    posted_on      DATE DEFAULT NULL,
    closing_on     DATE DEFAULT NULL,

    is_software_role TINYINT(1) DEFAULT 0,
    matched_keywords JSON,
    match_score     DOUBLE DEFAULT 0,
    match_level     VARCHAR(16) DEFAULT 'none',

    language        VARCHAR(16) DEFAULT '',
    raw_json        JSON,

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_url (source_url(255)),
    INDEX idx_company (company_name),
    INDEX idx_city (city),
    INDEX idx_country (country),
    INDEX idx_match_level (match_level),
    INDEX idx_posted_on (posted_on),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


class Database:
    def __init__(self, host: str, port: int, user: str, password: str, database: str, charset: str = "utf8mb4"):
        self.config = {
            "host": host, "port": port, "user": user, "password": password,
            "database": database, "charset": charset, "autocommit": True,
        }
        self._conn = None

    def connect(self):
        self._conn = pymysql.connect(**self.config)
        self._conn.ping(reconnect=True)

    def ensure_schema(self):
        with self._conn.cursor() as cur:
            cur.execute(DDL)

    def execute(self, sql: str, params=None):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def executemany(self, sql: str, params_list: list):
        with self._conn.cursor() as cur:
            cur.executemany(sql, params_list)

    def close(self):
        if self._conn:
            self._conn.close()
