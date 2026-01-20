from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Dict, List, Optional, Tuple
from urllib.request import pathname2url, url2pathname
from os import path, makedirs
import logging
from datetime import datetime
import time
from tzlocal import get_localzone
import re

from .utils import download
from .data import GeneralGroup, Proxy, ProxyGroup, Rule, RuleType
from .reader import ISubscribeReader

logger = logging.getLogger(__name__)


@dataclass
class RewriteRuleSpec:
    """Specification for a single rewrite rule."""

    rule_type: RuleType
    match: str
    new_strategy: str
    old_strategy: Optional[str] = None
    is_regex: bool = False

    @staticmethod
    def from_string(spec: str) -> "RewriteRuleSpec":
        """
        Parse from CLI string formats:
          - "RuleType,Match,Old-Strategy=New-Strategy"
          - "RuleType,Match=New-Strategy"
        Also supports legacy:
          - "RuleType,Match,New-Strategy"
        Match may be regex wrapped by "//".
        """
        if not spec:
            raise ValueError("empty rewrite rule specification")

        parts = spec.split(",", 2)
        if len(parts) < 2:
            raise ValueError(f'invalid rewrite rule format: "{spec}"')

        rule_type_str = parts[0].strip()
        try:
            rule_type = RuleType(rule_type_str)
        except ValueError as e:
            raise ValueError(f'invalid rule type "{rule_type_str}"') from e

        if len(parts) == 2:
            # "RuleType,Match=New-Strategy"
            rest = parts[1].strip()
            if "=" not in rest:
                raise ValueError(f'invalid rewrite rule format (missing "="): "{spec}"')
            match_part, new_strategy = rest.split("=", 1)
            old_strategy = None
        else:
            # len(parts) == 3:
            # "RuleType,Match,Old-Strategy=New-Strategy"
            # or legacy "RuleType,Match,New-Strategy"
            match_part = parts[1].strip()
            strategy_part = parts[2].strip()
            if "=" in strategy_part:
                old_strategy, new_strategy = strategy_part.split("=", 1)
                old_strategy = old_strategy.strip() or None
            else:
                old_strategy = None
                new_strategy = strategy_part

        match_raw = match_part.strip()
        is_regex = match_raw.startswith("/") and match_raw.endswith("/") and len(match_raw) >= 2
        match = match_raw[1:-1] if is_regex else match_raw

        new_strategy = new_strategy.strip()
        if not new_strategy:
            raise ValueError(f'new strategy cannot be empty in "{spec}"')

        return RewriteRuleSpec(
            rule_type=rule_type,
            match=match,
            new_strategy=new_strategy,
            old_strategy=old_strategy.strip() if old_strategy else None,
            is_regex=is_regex,
        )

    @staticmethod
    def from_config(obj: Dict) -> "RewriteRuleSpec":
        """Create from serialized config object."""
        rule_type_str = obj.get("rule_type")
        if not rule_type_str:
            raise ValueError("rewrite rule config missing 'rule_type'")
        rule_type = RuleType(rule_type_str)

        match = obj.get("match")
        if match is None:
            raise ValueError("rewrite rule config missing 'match'")

        new_strategy = obj.get("new_strategy")
        if not new_strategy:
            raise ValueError("rewrite rule config missing 'new_strategy'")

        old_strategy = obj.get("old_strategy")
        is_regex = bool(obj.get("is_regex", False))

        return RewriteRuleSpec(
            rule_type=rule_type,
            match=str(match),
            new_strategy=str(new_strategy),
            old_strategy=str(old_strategy) if old_strategy is not None else None,
            is_regex=is_regex,
        )

    def to_config(self) -> Dict:
        """Serialize to config object."""
        result: Dict[str, object] = {
            "rule_type": self.rule_type.value,
            "match": self.match,
            "new_strategy": self.new_strategy,
        }
        if self.old_strategy is not None:
            result["old_strategy"] = self.old_strategy
        if self.is_regex:
            result["is_regex"] = True
        return result

    def matches(self, rule: Rule) -> bool:
        """Check whether this rewrite rule applies to the given rule."""
        if rule.type == RuleType.MATCH:
            # MATCH rules don't have a match field
            return False
        if rule.type != self.rule_type:
            return False
        if self.old_strategy is not None and rule.strategy != self.old_strategy:
            return False

        target = rule.match
        if target is None:
            return False

        if self.is_regex:
            try:
                return re.search(self.match, target) is not None
            except re.error:
                # Should not happen if validated on creation, but be safe
                logger.warning("invalid regex in RewriteRuleSpec: %s", self.match)
                return False
        else:
            return target == self.match

    def __str__(self) -> str:
        """Human-readable/CLI representation."""
        match_display = f"/{self.match}/" if self.is_regex else self.match
        if self.old_strategy:
            return f"{self.rule_type.value},{match_display},{self.old_strategy}={self.new_strategy}"
        return f"{self.rule_type.value},{match_display}={self.new_strategy}"


class Info(object):

    name: str
    priority: int
    use_rules: bool
    proxies: Dict[str, Proxy]   # proxy name -> proxy
    proxy_groups_general: Dict[GeneralGroup, ProxyGroup]  # general group -> proxy group name -> proxy group
    proxy_groups_other: Dict[str, ProxyGroup]  # proxy group name -> proxy group
    rules: List[Rule]

    def __init__(
        self,
        reader: ISubscribeReader,
        name: str,
        priority: int,
        use_rules: bool,
        group_info: Optional[Dict[str, GeneralGroup]] = None,
        rewrite_rules: Optional[List[RewriteRuleSpec]] = None,
    ):
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
            if category is None or category == GeneralGroup.GLOBAL:
                self.proxy_groups_other[g.name] = g
            else:
                self.proxy_groups_general[category] = g
        if len(self.proxy_groups_general) == 0:
            category = group_info.get('*')
            if category is not None:
                self.proxy_groups_general[category] = reader.get_all_proxies(category.value)
        # self.rules
        self.rules = reader.get_rules()
        # apply rewrite rules
        if rewrite_rules:
            self._apply_rewrite_rules(rewrite_rules)

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
            if category == GeneralGroup.GLOBAL:
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
    
    def _apply_rewrite_rules(self, rewrite_rules: List[RewriteRuleSpec]) -> None:
        """Apply rewrite rules to modify rule strategies."""
        for spec in rewrite_rules:
            for rule in self.rules:
                try:
                    if spec.matches(rule):
                        rule.strategy = spec.new_strategy
                except Exception as e:
                    logger.warning("failed to apply rewrite rule %s: %s", spec, e)

def extract(info: Info) -> Tuple[List[Proxy], List[ProxyGroup], List[Rule]]:
    proxies = info.proxies
    proxy_groups_general = info.proxy_groups_general
    proxy_groups_other = info.proxy_groups_other
    rules = info.rules

    proxies_list = list(proxies.values())
    proxies_list.sort(key=lambda x: x.name)
    proxy_groups_list = list(proxy_groups_general.values())
    proxy_groups_list.extend(proxy_groups_other.values())
    for proxy_group in proxy_groups_list:
        proxy_group.rectify()
    rules = rules  #TODO: filter rules
    return (proxies_list, proxy_groups_list, rules)

def merge(data: List[Info]) -> Tuple[List[Proxy], List[ProxyGroup], List[Rule]]:
    # sort by priority from high to low
    data.sort(key=lambda x: x.priority)
    # merge
    proxies: Dict[str, Proxy] = OrderedDict()   # proxy name -> proxy
    proxy_groups_general: Dict[GeneralGroup, ProxyGroup] = OrderedDict()  # general group -> proxy group name -> proxy group
    proxy_groups_other: Dict[str, ProxyGroup] = OrderedDict()  # proxy group name -> proxy group
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
            if category == GeneralGroup.GLOBAL:
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
    for proxy_group in proxy_groups_list:
        proxy_group.rectify()
    rules = rules  #TODO: filter rules
    return (proxies_list, proxy_groups_list, rules)



LOCAL_FILE_PREFIX = 'file://'
LOCAL_FILE_SCHEME = 'file:'
LOCAL_FILE_SCHEME_LEN = len(LOCAL_FILE_SCHEME) # notice only remove 'file:'


class ProcessSettings(object):

    use_rules: bool # if to use rules; default=False

    general_group: Dict[str, GeneralGroup]  # how to map group info to GeneralGroup; default={}

    rewrite_rules: List[RewriteRuleSpec]  # list of rewrite rule specifications; default=[]

    def __init__(
        self,
        use_rules: bool = False,
        general_group: Optional[Dict[str, str]] = None,
        rewrite_rules: Optional[List] = None,
        **kwargs,
    ):
        self.use_rules = use_rules
        self.general_group = {}
        if general_group is not None:
            for k, v in general_group.items():
                try:
                    self.general_group[k] = GeneralGroup(v)
                except ValueError:
                    logger.warning('unknown general group value: %s, ignore', v)
                    continue
        self.rewrite_rules: List[RewriteRuleSpec] = []
        if rewrite_rules is not None:
            for item in rewrite_rules:
                try:
                    if isinstance(item, str):
                        spec = RewriteRuleSpec.from_string(item)
                    elif isinstance(item, dict):
                        spec = RewriteRuleSpec.from_config(item)
                    else:
                        logger.warning('unknown rewrite rule item type: %s', type(item))
                        continue
                    self.rewrite_rules.append(spec)
                except Exception as e:
                    logger.warning('invalid rewrite rule "%s": %s', item, e)
        if kwargs and len(kwargs) > 0:
            logger.warning('unknown process settings fields: %s, ignore', kwargs.keys())
    
    def serialize(self) -> Dict:
        result = {}
        if isinstance(self.use_rules, bool):
            result['use_rules'] = self.use_rules
        if self.general_group and len(self.general_group) > 0:
            gg = {}
            for k, v in self.general_group.items():
                gg[k] = v.value
            result['general_group'] = gg
        if self.rewrite_rules and len(self.rewrite_rules) > 0:
            result['rewrite_rules'] = [spec.to_config() for spec in self.rewrite_rules]
        return result
    
    def general_group_set(self, key: str, value: Optional[str]) -> None:
        if not value:
            if key in self.general_group:
                del self.general_group[key]
        else:
            try:
                self.general_group[key] = GeneralGroup(value)
            except ValueError:
                logger.warning('unknown general group value: %s, ignore', value)
    
    def rewrite_rule_add(self, rewrite_rule: str) -> None:
        """Add a rewrite rule specification from CLI string."""
        try:
            spec = RewriteRuleSpec.from_string(rewrite_rule)
        except ValueError as e:
            logger.warning('invalid rewrite rule "%s": %s', rewrite_rule, e)
            return
        if spec not in self.rewrite_rules:
            self.rewrite_rules.append(spec)
    
    def rewrite_rule_remove(self, rewrite_rule: str) -> None:
        """Remove a rewrite rule specification from CLI string."""
        try:
            spec = RewriteRuleSpec.from_string(rewrite_rule)
        except ValueError as e:
            logger.warning('invalid rewrite rule for removal "%s": %s', rewrite_rule, e)
            return
        self.rewrite_rules = [s for s in self.rewrite_rules if s != spec]


class Provider(object):

    name: str   # name of the provider; unique; required

    type: str   # type for reader factory; required

    _url: str   # url for download data from remote, or local file path with prefix 'file://'; required

    #mutable
    _cache: str  # cached file for downloaded data; default='' means no cache; should only be updated by @Provider

    ignore: bool  # whether to ignore this provider; default=False

    priority: int  # the priority of the provider; default=0

    update_interval: int  # update interval in seconds, when call @Provider.load only do download if last update is older than this; default=0; when -1 means never update

    #mutable
    last_update: int  # timestamp of last update (seconds since epoch); default=0 means no update yet; should only be updated by @Provider

    process_settings: Optional[ProcessSettings]  # settings for processing loaded data; default=None

    @property
    def url(self) -> str:
        return self._url
    
    @url.setter
    def url(self, value: str) -> None:
        if not value:
            raise ValueError('url cannot be empty')
        self._url = value
        self._cache = ''
        self.last_update = 0
    
    @property
    def local_file(self) -> Optional[str]:
        if self._url.startswith(LOCAL_FILE_PREFIX):
            local_path = url2pathname(self._url[LOCAL_FILE_SCHEME_LEN:])
            return local_path
        return None
    
    @local_file.setter
    def local_file(self, value: str) -> None:
        if not value:
            raise ValueError('local file path cannot be empty')
        self._url = Provider.get_local_file_url(value)
        self._cache = ''
        self.last_update = 0

    @property
    def cache(self) -> str:
        return self._cache
    

    def __init__(self, name: str, type: str = '', url: str = '', cache: str = '', file: str = '', ignore: bool = False, priority: int = 0, update_interval: int = 0, last_update: str = '', process_settings: Optional[Dict] = None, **kwargs):
        self.name = name
        self.type = type
        self._url = url
        self._cache = cache
        self._file = file
        self.ignore = ignore
        self.priority = priority
        self.update_interval = update_interval
        # Convert ISO 8601 string to epoch timestamp
        self.last_update = 0
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=get_localzone())
                self.last_update = int(dt.timestamp())
            except ValueError:
                logger.warning('invalid last_update format: %s, using 0', last_update)
        # Process settings
        self.process_settings = None
        if process_settings is not None:
            self.process_settings = ProcessSettings(**process_settings)
        if kwargs and len(kwargs) > 0:
            logger.warning('unknown provider fields: %s, ignore', kwargs.keys())

    def serialize(self) -> Dict:
        result = {}
        result['name'] = self.name
        result['type'] = self.type
        if self._url:
            result['url'] = self._url
        if self._cache:
            result['cache'] = self._cache
        if self._file:
            result['file'] = self._file
        if self.ignore:
            result['ignore'] = self.ignore
        result['priority'] = self.priority
        result['update_interval'] = self.update_interval
        if self.last_update > 0:
            dt = datetime.fromtimestamp(self.last_update, tz=get_localzone())
            result['last_update'] = dt.isoformat()
        if self.process_settings is not None:
            result['process_settings'] = self.process_settings.serialize()
        return result
    
    def is_local(self) -> bool:
        return self._url.startswith(LOCAL_FILE_PREFIX)
    
    def load(self, reader_factory: Callable[[str], ISubscribeReader], cache_root: str) -> Info:
        reader = reader_factory(self.type)
        local_file_path = self.local_file
        if local_file_path:
            self._load_local(local_file_path, reader)
        else:
            self._load_remote(self._url, reader, cache_root)
        use_rules = self.process_settings.use_rules if self.process_settings is not None else False
        group_info = self.process_settings.general_group if self.process_settings is not None else None
        rewrite_rules = self.process_settings.rewrite_rules if self.process_settings is not None else None
        return Info(reader, self.name, self.priority, use_rules, group_info, rewrite_rules)
    
    def update(self, reader_factory: Callable[[str], ISubscribeReader], cache_root: str) -> bool:
        reader = reader_factory(self.type)
        if self.is_local():
            raise ValueError('cannot update local file provider')
        return self._load_remote(self._url, reader, cache_root, force_update=True)
        
    
    def _load_remote(self, url: str, reader: ISubscribeReader, cache_root: str, force_update: bool = False) -> bool:
        content: Optional[bytes] = None
        cache_file: Optional[str] = None
        # check if need update
        need_update = False
        if not self._cache:
            need_update = True
        elif force_update:
            need_update = self.update_interval >= 0
        elif self.update_interval >= 0:
            current_time = int(time.time())
            if current_time - self.last_update >= self.update_interval:
                need_update = True
        logger.debug('Provider{%s} load remote %s need update: %s', self.name, url, need_update)
        if need_update:
            try:
                logger.info('Provider{%s} downloading from %s', self.name, url)
                content, file_name = download(url)
                if file_name and Provider._is_valid_filename(file_name):
                    file_name_main, file_name_ext = path.splitext(file_name)
                    cache_file = reader.get_cache_name(file_name_main)
                if cache_file is None:
                    cache_file = reader.get_cache_name('config')
                cache_file = path.join(cache_root, self.name, cache_file)
                logger.info('Provider{%s} downloaded %s from %s', self.name, file_name or '<file>', url)
            except Exception as e:
                if self._cache:
                    logger.warning('Provider{%s} download failed for %s, try load cache %s: %s', self.name, url, self._cache, e)
                    self._load_cache(self._cache, reader)
                    logger.info('Provider{%s} loaded from cache %s', self.name, self._cache)
                    return False
                raise e
            with BytesIO(content) as ifile:
                # ensure cache directory exists
                cache_dir = path.dirname(cache_file)
                if not path.exists(cache_dir):
                    makedirs(cache_dir, exist_ok=True)
                with open(cache_file, 'wb') as ofile_cache:
                    reader.read(ifile, False, ofile_cache)
                    self._cache = cache_file
                    self.last_update = int(time.time())
            logger.info('Provider{%s} loaded from remote %s and cached to %s', self.name, url, cache_file)
            return True
        else:
            logger.info('Provider{%s} loading from cache %s', self.name, self._cache)
            self._load_cache(self._cache, reader)
            logger.info('Provider{%s} loaded from cache %s', self.name, self._cache)
            return False
    
    def _load_local(self, local: str, reader: ISubscribeReader):
        logger.info('Provider{%s} loading from local file %s', self.name, local)
        with open(local, 'rb') as ifile:
            reader.read(ifile, False, None)
        logger.info('Provider{%s} loaded from local file %s', self.name, local)

    def _load_cache(self, cache: str, reader: ISubscribeReader):
        with open(cache, 'rb') as ifile:
            reader.read(ifile, True, None)

    @staticmethod
    def get_local_file_url(file_path: str) -> str:
        p = path.abspath(file_path)
        return LOCAL_FILE_SCHEME + pathname2url(p)


    @staticmethod
    def _is_valid_filename(filename: str) -> bool:
        invalid_chars = set('<>:"/\\|?*')
        for ch in filename:
            if ch in invalid_chars:
                return False
        return True