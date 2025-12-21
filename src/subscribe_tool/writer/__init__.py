"""Config writer interface and implementations"""

from abc import ABC, abstractmethod
from typing import List, BinaryIO

from ..data import Proxy, ProxyGroup, Rule


class IConfigWriter(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def get_target_file_name(self, filename: str) -> str:
        pass

    @abstractmethod
    def template(self, ifile: BinaryIO) -> None:
        pass

    @abstractmethod
    def write(self, ofile: BinaryIO, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: List[Rule], **kwargs) -> None:
        pass


__all__ = ['IConfigWriter']
