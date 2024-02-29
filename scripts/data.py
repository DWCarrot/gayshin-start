from abc import ABC, abstractmethod
from enum import Enum
from io import TextIOWrapper, BufferedIOBase
import json
from typing import BinaryIO, Callable, Dict, List, Set, Tuple


class Proxy(object):

    inner: dict

    def __init__(self, inner: Dict):
        self.inner = inner

    @property
    def name(self) -> str:
        return self.inner['name']
    
    @name.setter
    def name(self, name: str):
        self.inner['name'] = name

    def __repr__(self) -> str:
        return self.inner.__repr__()


class ProxyGroup(object):

    inner: dict

    def __init__(self, inner: Dict):
        self.inner = inner
        if not 'proxies' in self.inner:
            raise ValueError('\"proxies\" not found in proxy group')
        if 'use' in self.inner:
            raise ValueError('\"use\" unimplemented in proxy group')
        if 'include-all' in self.inner:
            raise ValueError('\"include-all\" unimplemented in proxy group')
        if 'include-all-proxies' in self.inner:
            raise ValueError('\"include-all-proxies\" unimplemented in proxy group')
        if 'include-all-providers' in self.inner:
            raise ValueError('\"include-all-providers\" unimplemented in proxy group')
        if 'filter' in self.inner:
            raise ValueError('\"filter\" unimplemented in proxy group')
        if 'exclude-filter' in self.inner:
            raise ValueError('\"exclude-filter\" unimplemented in proxy group')
        if 'exclude-type' in self.inner:
            raise ValueError('\"exclude-type\" unimplemented in proxy group')

    @property
    def name(self) -> str:
        return self.inner['name']


    @name.setter
    def name(self, name: str):
        self.inner['name'] = name

    def modify_proxy(self, modifier: Callable[[str], None]) -> bool:
        proxies = self.inner['proxies']
        if proxies is not None:
            for i in range(len(proxies)):
                proxies[i] = modifier(proxies[i])

    def __repr__(self) -> str:
        return self.inner.__repr__()


class RuleType(Enum):
    DOMAIN = 'DOMAIN'
    DOMAIN_SUFFIX = 'DOMAIN-SUFFIX'
    DOMAIN_KEYWORD = 'DOMAIN-KEYWORD'
    IP_CIDR = 'IP-CIDR'
    IP_CIDR6 = 'IP-CIDR6'
    DST_PORT = 'DST-PORT'
    SRC_PORT = 'SRC-PORT'
    PROCESS_NAME = 'PROCESS-NAME'
    PROCESS_PATH = 'PROCESS-PATH'
    LOGICAL_AND = 'AND'
    LOGICAL_OR = 'OR'
    LOGICAL_NOT = 'NOT'
    GEOSITE = 'GEOSITE'
    GEOIP = 'GEOIP'
    IN_TYPE = 'IN-TYPE'
    IN_USER = 'IN-USER'
    IN_NAME = 'IN-NAME'
    NETWORK = 'NETWORK'
    RULE_SET = 'RULE-SET'
    SUB_RULE = 'SUB-RULE'
    MATCH = 'MATCH'


class Rule(object):

    type: RuleType
    match: str
    strategy: str
    no_resolve: bool | None

    def __init__(self, raw: str):
        inside = 0
        last = 0
        parts = []
        for i, c in enumerate(raw):
            if c == ',' and inside == 0:
                parts.append(raw[last:i])
                last = i + 1
            elif c == '(':
                inside += 1
            elif c == ')':
                inside -= 1
        if inside == 0:
            if last < len(raw):
                parts.append(raw[last:])
        else:
            raise ValueError('Invalid rule format')
        self.type = RuleType(parts[0])
        if self.type == RuleType.MATCH:
            self.match = None
            self.strategy = parts[1]
            self.no_resolve = None
        else:
            self.match = parts[1]
            self.strategy = parts[2]
            if len(parts) > 3:
                self.no_resolve = parts[3] == 'no-resolve'
            else:
                self.no_resolve = None

    @property
    def raw(self) -> str:
        if self.match is None:
            return f'{self.type.value},{self.strategy}'
        elif self.no_resolve:
            return f'{self.type.value},{self.match},{self.strategy},no-resolve'
        else:
            return f'{self.type.value},{self.match},{self.strategy}'
    
    def __repr__(self) -> str:
        return self.raw



class ISubscribeReader(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def get_cache_name(self, filename: str) -> str:
        pass

    @abstractmethod
    def read(self, ifile: BufferedIOBase, is_cache: bool, ofile_cache: BufferedIOBase | None = None) -> None:
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
    def get_rules(self, name: str) -> List[Rule]:
        pass



class IConfigWriter(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def template(self, ifile: BufferedIOBase) -> None:
        pass

    @abstractmethod
    def write(self, ofile: BufferedIOBase, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: Dict[str, List[Rule]], **kwargs) -> None:
        pass



class GeneralGroup(Enum):
    # DIRECT = 'DIRECT'
    # REJECT = 'REJECT'
    PROXY = 'PROXY'
    _GLOBAL = 'GLOBAL'


class Info(object):

    name: str
    priority: int
    use_rules: bool
    proxies: Dict[str, Proxy]   # proxy name -> proxy
    proxy_groups_general: Dict[GeneralGroup, ProxyGroup]  # general group -> proxy group name -> proxy group
    proxy_groups_other: Dict[str, ProxyGroup]  # proxy group name -> proxy group
    rules: Dict[str, List[Rule]] # rule name / root -> rule

    def __init__(self, reader: ISubscribeReader, name: str, priority: int, use_rules: bool, group_info: Dict[str, GeneralGroup] | None = None):
        self.name = name
        self.priority = priority
        self.use_rules = use_rules
        # self.proxies
        proxies_raw = reader.get_proxies()
        self.proxies = {}
        for p in proxies_raw:
            self.proxies[p.name] = p
        # self.proxy_groups
        proxy_groups_raw = reader.get_proxy_groups()
        if group_info is None:
            group_info = {}
        self.proxy_groups_general = {}
        self.proxy_groups_other = {}
        for g in proxy_groups_raw:
            category = group_info.get(g.name)
            if category is None or category == GeneralGroup._GLOBAL:
                self.proxy_groups_other[g.name] = g
            else:
                self.proxy_groups_general[category] = g
        self.proxy_groups_general[GeneralGroup._GLOBAL] = reader.get_all_proxies(GeneralGroup._GLOBAL.value)
        # self.rules
        rules_root_raw = reader.get_rules(None)
        self.rules = {}
        self.rules[''] = rules_root_raw
        for r in rules_root_raw:
            if r.type == RuleType.SUB_RULE:
                sub_rules_raw = reader.get_rules(r.match)
                self.rules[r.strategy] = sub_rules_raw

    def modify_by_name(self, prefix: str) -> None:
        # modify proxy name
        proxies_names = {}
        for name, p in self.proxies.items():
            new_name = f'[{prefix}]-{name}'
            proxies_names[p.name] = new_name
            p.name = new_name
        # modify proxy group name
        proxy_groups_names = {}
        for category, g in self.proxy_groups_general.items():
            new_name = category.value
            if category == GeneralGroup._GLOBAL:
                new_name = f'[{prefix}]'
            else:
                proxy_groups_names[g.name] = new_name
            g.name = new_name
        for name, g in self.proxy_groups_other.items():
            new_name = f'[{prefix}]-{name}'
            proxy_groups_names[g.name] = new_name
            g.name = new_name
        # modify proxy name in proxy group
        def inner_modifier(name: str) -> str:
            new_name = proxies_names.get(name)
            if new_name is not None:
                return new_name
            new_name = proxy_groups_names.get(name)
            if new_name is not None:
                return new_name
            return name
        for category, g in self.proxy_groups_general.items():
            g.modify_proxy(inner_modifier)
        for name, g in self.proxy_groups_other.items():
            g.modify_proxy(inner_modifier)
        # modify rule strategy
        for name, rules in self.rules.items():
            for r in rules:
                r.strategy = inner_modifier(r.strategy)
            #TODO: modify sub-rule name

def merge(data: List[Info]) -> Tuple[List[Proxy], List[ProxyGroup], Dict[str, List[Rule]]]:
    # sort by priority from high to low
    data.sort(key=lambda x: x.priority)
    # merge
    proxies: Dict[str, Proxy] = {}   # proxy name -> proxy
    proxy_groups_general: Dict[GeneralGroup, ProxyGroup] = {}  # general group -> proxy group name -> proxy group
    proxy_groups_other: Dict[str, ProxyGroup] = {}  # proxy group name -> proxy group
    rules: Dict[str, List[Rule]] = {} # rule name / root -> rule
    # iterate
    for info in data:
        # merge proxies: keep larger priority
        for name, p in info.proxies.items():
            old_p = proxies.get(p.name)
            if old_p is None:
                proxies[p.name] = p
        # merge proxy groups: keep larger priority and merge proxies
        for category, g in info.proxy_groups_general.items():
            if category == GeneralGroup._GLOBAL:
                old_g = proxy_groups_other.get(g.name)
                if old_g is None:
                    proxy_groups_other[g.name] = g
            else:
                old_g = proxy_groups_general.get(category)
                if old_g is None:
                    proxy_groups_general[category] = g
                else:
                    old_g_proxies = old_g.inner.get('proxies')
                    g_proxies = g.inner.get('proxies')
                    if old_g_proxies is not None and g_proxies is not None:
                        old_g_proxies = set(old_g_proxies)
                        old_g_proxies.update(g_proxies)
                        old_g.inner['proxies'] = list(old_g_proxies)
        # merge other proxy groups: keep larger priority
        for name, g in info.proxy_groups_other.items():
            old_g = proxy_groups_other.get(g.name)
            if old_g is None:
                proxy_groups_other[g.name] = g
        # merge rules: keep larger priority
        if info.use_rules:
            for name, rs in info.rules.items():
                old_rules = rules.get(name)
                if old_rules is None:
                    rules[name] = rs
                else:
                    old_rules.extend(rs)
    proxies_list = list(proxies.values())
    proxy_groups_list = list(proxy_groups_general.values())
    proxy_groups_list.extend(proxy_groups_other.values())
    rules = rules #TODO: filter rules
    return (proxies_list, proxy_groups_list, rules)



if __name__ == '__main__':
    print('This is a library, not a standalone script')