"""Subscribe reader interface and implementations"""

from abc import ABC, abstractmethod
from typing import List, BinaryIO

from ..data import Proxy, ProxyGroup, Rule


class ISubscribeReader(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def load(self, ifile: BinaryIO, is_cache: bool) -> None:
        """Load config from input file."""
        pass

    @abstractmethod
    def get_cache_name(self, filename: str) -> str:
        """Return cache file name for the given base filename."""
        pass

    @abstractmethod
    def dump(self, ofile: BinaryIO) -> None:
        """Write loaded config to output file (for cache)."""
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
