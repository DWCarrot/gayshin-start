"""Clash config writer implementation"""

import logging
from typing import BinaryIO, Dict, List, Optional

from . import IConfigWriter
from ..data import Proxy, ProxyGroup, Rule

logger = logging.getLogger(__name__)

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    logger.warning(f'unable to load libyaml; use python module instead: {e}')
    from yaml import Loader, Dumper
from jinja2 import Template

from ..utils import insert_in_list

PROXY_PLACEHOLDER = '__PROXY_PLACEHOLDER__'
PROXY_GROUP_PLACEHOLDER = '__PROXY_GROUP_PLACEHOLDER__'
RULE_PLACEHOLDER = '__RULE_PLACEHOLDER__'

class ClashConfigWriter(IConfigWriter):

    _template: Optional[Template]

    def __init__(self):
        super().__init__()
        self._template = None

    def get_target_file_name(self, filename: str) -> str:
        if not filename.lower().endswith('.yaml') and not filename.lower().endswith('.yml'):
            return f'{filename}.yaml'
        return filename

    def template(self, ifile: BinaryIO) -> None:
        content = ifile.read().decode('utf-8')
        self._template = Template(content)

    def write(self, ofile: BinaryIO, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: List[Rule], **kwargs) -> None:
        if self._template is None:
            raise ValueError('template not initialized')
        content = self._template.render(**kwargs)
        loader = Loader(stream=content)
        template = None
        try:
            template = loader.get_single_data()
        finally:
            loader.dispose()
        template_proxies = template.get('proxies')
        template['proxies'] = insert_in_list(template_proxies, lambda x: x.get('name') == PROXY_PLACEHOLDER, [p.inner for p in proxies])
        template_proxy_groups = template.get('proxy-groups')
        template['proxy-groups'] = insert_in_list(template_proxy_groups, lambda x: x.get('name') == PROXY_GROUP_PLACEHOLDER, [pg.inner for pg in proxy_groups])
        template_rules = template.get('rules')
        template['rules'] = insert_in_list(template_rules, lambda x: x == RULE_PLACEHOLDER, [rule.raw for rule in rules])
        dumper = Dumper(stream=ofile, encoding='utf-8', allow_unicode=True, sort_keys=False)
        try:
            dumper.open()
            dumper.represent(template)
            dumper.close()
        finally:
            dumper.dispose()
