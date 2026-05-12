from abc import ABC, abstractmethod

from models.job import Job
from models.source import SourceConfig


class Collector(ABC):
    """采集器抽象基类，每种数据源实现各自的采集逻辑"""

    def __init__(self, config: SourceConfig):
        self.config = config

    @abstractmethod
    def fetch(self) -> list[Job]:
        """从数据源获取原始岗位列表并返回统一 Job 模型"""
        ...
