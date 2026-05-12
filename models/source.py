from dataclasses import dataclass, field
from typing import Optional

from models.enums import SourceType


@dataclass
class SourceConfig:
    name: str
    name_cn: str
    type: SourceType
    url: str
    china_locations: list[str] = field(default_factory=list)
    enabled: bool = True

    # ATS specific
    board_token: Optional[str] = None      # Greenhouse
    site: Optional[str] = None              # Lever
    tenant: Optional[str] = None            # Workday
    wd_server: Optional[str] = None         # Workday

    # Generic web specific
    selectors: Optional[dict] = None
