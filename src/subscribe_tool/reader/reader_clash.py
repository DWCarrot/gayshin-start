"""Clash subscribe reader implementation"""

import logging
from typing import BinaryIO, Optional, Dict, List

from . import ISubscribeReader
from ..data import Proxy, ProxyGroup, Rule

logger = logging.getLogger(__name__)

try:
    from yaml import CLoader as Loader
except ImportError as e:
    logger.warning(f'unable to load libyaml; use python module instead: {e}')
    from yaml import Loader


class ClashSubscribeReader(ISubscribeReader):
    
    inner: Dict

    def __init__(self):
        super().__init__()

    def get_cache_name(self, filename: str) -> str:
        return filename + '.yml'

    def read(self, ifile: BinaryIO, is_cache: bool, ofile_cache: Optional[BinaryIO] = None) -> None:
        loader = Loader(ifile) # TODO: encoding?
        try:
            self.inner = loader.get_single_data()
        finally:
            loader.dispose()
        if not is_cache and ofile_cache is not None:
            ifile.seek(0)
            while True:
                data = ifile.read(1024)
                if not data:
                    break
                ofile_cache.write(data)


    def get_proxies(self) -> List[Proxy]:
        proxies = self.inner.get('proxies')
        if proxies is None:
            return None
        result = list()
        for p in proxies:
            try:
                result.append(Proxy(p))
            except Exception as e:
                logger.warning(f'invalid proxy: {p}: {e}')
        return result
    
    def get_all_proxies(self, name: str) -> ProxyGroup:
        proxies = self.inner.get('proxies')
        if proxies is None:
            return None
        inner = {
            'name': name,
            'type': 'select',
            'proxies': [p['name'] for p in proxies]
        }
        return ProxyGroup(inner)

    def get_proxy_groups(self) -> List[ProxyGroup]:
        proxy_groups = self.inner.get('proxy-groups')
        if proxy_groups is None:
            return []
        result = list()
        for pg in proxy_groups:
            try:
                result.append(ProxyGroup(pg))
            except Exception as e:
                print(f'>! invalid proxy group: {pg}', e)
        return result
    
    def get_rules(self) -> List[Rule]:
        rules = self.inner.get('rules')
        if rules is None:
            return []
        result = list()
        for rule_raw in rules:
            try:
                result.append(Rule(rule_raw))
            except Exception as e:
                print(f'>! invalid rule: {rule_raw}', e)
        return result
