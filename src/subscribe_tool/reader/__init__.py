"""Subscribe reader interface and implementations"""

from abc import ABC, abstractmethod
from typing import List, Optional, BinaryIO

from ..data import Proxy, ProxyGroup, Rule


class ISubscribeReader(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def get_cache_name(self, filename: str) -> str:
        pass

    @abstractmethod
    def read(self, ifile: BinaryIO, is_cache: bool, ofile_cache: Optional[BinaryIO] = None) -> None:
        pass

    @abstractmethod
    def get_proxies(self) -> List[Proxy]:
        pass

    @abstractmethod
    def get_all_proxies(self, name: str) -> ProxyGroup:
        pass

    @abstractmethod
    def get_proxy_groups(self) -> List[ProxyGroup]:
        pass

    @abstractmethod
    def get_rules(self) -> List[Rule]:
        pass


__all__ = ['ISubscribeReader']
