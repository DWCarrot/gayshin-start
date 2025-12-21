from enum import Enum
from io import BufferedIOBase
from typing import Callable, Dict, List, Optional, Set, Tuple


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







class GeneralGroup(Enum):
    # DIRECT = 'DIRECT'
    # REJECT = 'REJECT'
    PROXY = 'PROXY'
    GLOBAL = 'GLOBAL'

