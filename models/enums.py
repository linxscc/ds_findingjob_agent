from enum import Enum


class SourceType(Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    GENERIC_WEB = "generic_web"
    MANUAL = "manual"


class WorkplaceType(Enum):
    ON_SITE = "on_site"
    REMOTE = "remote"
    HYBRID = "hybrid"
    UNSPECIFIED = "unspecified"


class EmploymentType(Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"
    UNSPECIFIED = "unspecified"


class MatchLevel(Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    NONE = "none"
