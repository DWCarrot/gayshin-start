from abc import ABC, abstractmethod
from enum import Enum
from io import BufferedIOBase
from typing import BinaryIO, Callable, Dict, List, Optional, Set, Tuple


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

    @property
    def type(self) -> str:
        return self.inner['type']

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

    def rectify(self) -> None:
        proxies = self.inner['proxies']
        if proxies is not None:
            proxies.sort()

    def __repr__(self) -> str:
        return self.inner.__repr__()
    
    def copy(self, name: str):
        new_inner = self.inner.copy()
        new_inner['name'] = name
        return ProxyGroup(new_inner)


class RuleType(Enum):
    DOMAIN = 'DOMAIN'
    DOMAIN_SUFFIX = 'DOMAIN-SUFFIX'
    DOMAIN_KEYWORD = 'DOMAIN-KEYWORD'
    DOMAIN_WILDCARD = 'DOMAIN-WILDCARD'
    DOMAIN_REGEX = 'DOMAIN-REGEX'
    GEOSITE = 'GEOSITE'
    IP_CIDR = 'IP-CIDR'
    IP_CIDR6 = 'IP-CIDR6'
    IP_SUFFIX = 'IP-SUFFIX'
    IP_ASN = 'IP-ASN'
    GEOIP = 'GEOIP'
    SRC_GEOIP = 'SRC-GEOIP'
    SRC_IP_ASN = 'SRC-IP-ASN'
    SRC_IP_CIDR = 'SRC-IP-CIDR'
    SRC_IP_SUFFIX = 'SRC-IP-SUFFIX'
    DST_PORT = 'DST-PORT'
    SRC_PORT = 'SRC-PORT'
    IN_PORT = 'IN-PORT'
    IN_TYPE = 'IN-TYPE'
    IN_USER = 'IN-USER'
    IN_NAME = 'IN-NAME'
    PROCESS_PATH = 'PROCESS-PATH'
    PROCESS_PATH_REGEX = 'PROCESS-PATH-REGEX'
    PROCESS_NAME = 'PROCESS-NAME'
    PROCESS_NAME_REGEX = 'PROCESS-NAME-REGEX'
    UID = 'UID'
    NETWORK = 'NETWORK'
    DSCP = 'DSCP'
    RULE_SET = 'RULE-SET'
    LOGICAL_AND = 'AND'
    LOGICAL_OR = 'OR'
    LOGICAL_NOT = 'NOT'
    SUB_RULE = 'SUB-RULE'
    MATCH = 'MATCH'


class Rule(object):

    type: RuleType
    match: str
    strategy: str
    no_resolve: Optional[bool]
    #src: Optional[str]

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
        if self.type in (RuleType.LOGICAL_AND, RuleType.LOGICAL_OR, RuleType.LOGICAL_NOT, RuleType.SUB_RULE):
            raise ValueError(f'unimplemented rule type: {self.type}')
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



class IConfigWriter(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def template(self, ifile: BinaryIO) -> None:
        pass

    @abstractmethod
    def write(self, ofile: BinaryIO, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: List[Rule], **kwargs) -> None:
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
    rules: List[Rule]

    def __init__(self, reader: ISubscribeReader, name: str, priority: int, use_rules: bool, group_info: Optional[Dict[str, GeneralGroup]] = None):
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
        if len(self.proxy_groups_general) == 0:
            category = group_info.get('*')
            if category is not None:
                self.proxy_groups_general[category] = reader.get_all_proxies(category.value)
        # self.rules
        self.rules = reader.get_rules()

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
        for r in self.rules:
            r.strategy = inner_modifier(r.strategy)
            #TODO: modify sub-rule name

def merge(data: List[Info]) -> Tuple[List[Proxy], List[ProxyGroup], List[Rule]]:
    # sort by priority from high to low
    data.sort(key=lambda x: x.priority)
    # merge
    proxies: Dict[str, Proxy] = {}   # proxy name -> proxy
    proxy_groups_general: Dict[GeneralGroup, ProxyGroup] = {}  # general group -> proxy group name -> proxy group
    proxy_groups_other: Dict[str, ProxyGroup] = {}  # proxy group name -> proxy group
    rules: List[Rule] = [] # rule name / root -> rule
    # iterate
    for info in data:
        # merge proxies: keep larger priority
        for name, p in info.proxies.items():
            old_p = proxies.get(p.name)
            if old_p is None:
                proxies[p.name] = p
        # merge proxy groups: keep larger priority and merge proxies
        total_proxies = None
        for category, g in info.proxy_groups_general.items():
            if category == GeneralGroup._GLOBAL:
                old_g = proxy_groups_other.get(g.name)
                if old_g is None:
                    proxy_groups_other[g.name] = g
                total_proxies = g.copy(f'[{info.name}]')
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
                if total_proxies is None and category == GeneralGroup.PROXY:
                    total_proxies = g.copy(f'[{info.name}]')
        # add general group to proxy groups
        if total_proxies is not None:
            proxy_groups_other[total_proxies.name] = total_proxies
        # merge other proxy groups: keep larger priority
        for name, g in info.proxy_groups_other.items():
            old_g = proxy_groups_other.get(g.name)
            if old_g is None:
                proxy_groups_other[g.name] = g
        # merge rules: keep larger priority
        if info.use_rules:
            rules.extend(info.rules)
    proxies_list = list(proxies.values())
    proxies_list.sort(key=lambda x: x.name)
    proxy_groups_list = list(proxy_groups_general.values())
    proxy_groups_list.extend(proxy_groups_other.values())
    proxy_groups_list.sort(key=lambda x: x.name)
    for proxy_group in proxy_groups_list:
        proxy_group.rectify()
    rules = rules  #TODO: filter rules
    return (proxies_list, proxy_groups_list, rules)



if __name__ == '__main__':
    print('This is a library, not a standalone script')