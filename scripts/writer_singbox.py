from io import TextIOWrapper
from typing import Any, BinaryIO, Dict, List, Optional, Set, Tuple
from collections import OrderedDict

from jinja2 import Template
from data import IConfigWriter, Proxy, ProxyGroup, Rule, RuleType
from pyjson5 import loads as json5_loads
from json import dump as json_dump

from utils import insert_in_list

CLASH2SINGBOX_ALLOWED_RULETYPES: Dict[RuleType, str] = {
    RuleType.DOMAIN: 'domain',
    RuleType.DOMAIN_SUFFIX: 'domain_suffix',
    RuleType.DOMAIN_KEYWORD: 'domain_keyword',
    #RuleType.DOMAIN_WILDCARD: None,   # not supported in singbox
    RuleType.DOMAIN_REGEX: 'domain_regex',
    RuleType.GEOSITE: 'geosite',    # ruleset
    RuleType.IP_CIDR: 'ip_cidr',
    RuleType.IP_CIDR6: 'ip_cidr',
    #RuleType.IP_SUFFIX: None,   # not supported in singbox
    #RuleType.IP_ASN: None,    # not supported in singbox
    RuleType.GEOIP: 'geoip',   # ruleset
    RuleType.SRC_GEOIP: 'src_geoip',   # ruleset
    #RuleType.SRC_IP_ASN: None,   # not supported in singbox
    RuleType.SRC_IP_CIDR: 'src_ip_cidr',
    #RuleType.SRC_IP_SUFFIX: None,   # not supported in singbox
    RuleType.DST_PORT: 'port;port_range',
    RuleType.SRC_PORT: 'src_port;src_port_range',
    RuleType.IN_PORT: None, # not supported in singbox
    RuleType.IN_TYPE: None, # not supported in singbox
    RuleType.IN_USER: None, # not supported in singbox
    RuleType.IN_NAME: None, # not supported in singbox
    RuleType.PROCESS_PATH: 'process_path',
    RuleType.PROCESS_PATH_REGEX: 'process_path_regex',
    RuleType.PROCESS_NAME: 'process_name',
    RuleType.PROCESS_NAME_REGEX: 'process_name_regex',
    RuleType.UID: 'user_id',
    RuleType.NETWORK: 'network',
    #RuleType.DSCP: None, # not supported in singbox
    RuleType.RULE_SET: '',
    RuleType.MATCH: ''
}

CLASH2SINGBOX_GROUP_DOMAIN_KEYS: Set[RuleType] = {
    RuleType.DOMAIN,
    RuleType.DOMAIN_SUFFIX,
    RuleType.DOMAIN_KEYWORD,
    RuleType.DOMAIN_REGEX,
    RuleType.IP_CIDR,
    RuleType.IP_CIDR6
}

SINGBOX_GEOIP_RULESET: Dict[str, Dict] = {
    'CN': {
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-cn.srs",
        "download_detour": "proxy"
    },
    'US': {
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-us.srs",
        "download_detour": "proxy"
    },
}

SINGBOX_GEOSITE_RULESET: Dict[str, Dict] = {
    'CN': {
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-cn.srs",
        "download_detour": "proxy"
    }
}

class Clash2SingboxTransformer:

    geoip: Dict[str, Any]
    geosite: Dict[str, Any]
    match_rule_target: Optional[str]

    def __init__(self):
        self.geoip = dict()
        self.geosite = dict()
        self.match_rule_target = None

    def transform_proxy(self, proxy: Proxy) -> dict:
        match proxy.type:
            case 'vmess':
                return self._vmess_transform(proxy.inner)
            case 'ss':
                return self._ss_transform(proxy.inner)
            case _:
                raise NotImplementedError(f"Proxy type '{proxy.type}' is not supported yet.")
            
    def transform_proxy_group(self, group: ProxyGroup) -> dict:
        # TODO: handle url test: "type": "urltest"
        result = {
            'type': 'selector',
            'tag': group.name,
            'outbounds': group.inner['proxies'],
        }
        return result
    
    def transform_rules(self, rules: List[Rule]) -> List[dict]:
        # group by target
        rules_grouped: OrderedDict[str, List[Rule]] = OrderedDict()
        for rule in rules:
            tgt = CLASH2SINGBOX_ALLOWED_RULETYPES.get(rule.type)
            if tgt is None:
                # TODO: log
                print(f'>! rule type {rule.type} is not supported in singbox, skipped')
                continue
            target = rule.strategy
            rule_grouped_items = rules_grouped.get(target)
            if rule_grouped_items is None:
                rule_grouped_items = []
                rules_grouped[target] = rule_grouped_items
            rule_grouped_items.append(rule)
        result = list()
        match_rule = None
        for outbound, rules in rules_grouped.items():
            print(f'> {len(rules)} rules to {outbound}')
            group_domain: Optional[Dict[str, List]] = None # field -> values # domain || domain_suffix || domain_keyword || domain_regex || [geosite] || [geoip] || ip_cidr || ip_is_private
            group_geosite: Optional[Dict[str, Any]] = None # GEO-KEY -> value geosite
            group_geoip: Optional[Dict[str, Any]] = None # GEO-KEY -> value # geoip
            group_port: Optional[Dict[str, List]] = None # field -> values # port || port_range
            group_src_ip: Optional[Dict[str, List]] = None # field -> values # [source_geoip] || source_ip_cidr || source_ip_is_private
            group_src_geoip: Optional[Dict[str, Any]] = None # GEO-KEY -> value # source_geoip
            group_src_port: Optional[Dict[str, List]] = None # field -> values # src_port || src_port_range
            group_others: OrderedDict[RuleType, Dict[str, Any]] = OrderedDict() # other rules that cannot be grouped
            for rule in rules:
                if rule.type in CLASH2SINGBOX_GROUP_DOMAIN_KEYS:
                    if group_domain is None:
                        group_domain = dict()
                    field = CLASH2SINGBOX_ALLOWED_RULETYPES[rule.type]
                    values = Clash2SingboxTransformer.get_or_default(group_domain, field)
                    values.append(rule.match)
                elif rule.type == RuleType.GEOSITE:
                    if group_geosite is None:
                        group_geosite = dict()
                    group_geosite[rule.match] = True
                elif rule.type == RuleType.GEOIP:
                    if group_geoip is None:
                        group_geoip = dict()
                    group_geoip[rule.match] = True
                elif rule.type == RuleType.DST_PORT:
                    if group_port is None:
                        group_port = dict()
                    single, ranges = Clash2SingboxTransformer.parse_port_range(rule.match)
                    if len(single) > 0:
                        values = Clash2SingboxTransformer.get_or_default(group_port, 'port')
                        values.extend(single)
                    if len(ranges) > 0:
                        values = Clash2SingboxTransformer.get_or_default(group_port, 'port_range')
                        values.extend([f'{r[0]}:{r[1]}' for r in ranges])
                elif rule.type == RuleType.SRC_IP_CIDR:
                    if group_src_ip is None:
                        group_src_ip = dict()
                    field = CLASH2SINGBOX_ALLOWED_RULETYPES[rule.type]
                    values = Clash2SingboxTransformer.get_or_default(group_src_ip, field)
                    values.append(rule.match)
                elif rule.type == RuleType.SRC_GEOIP:
                    if group_src_geoip is None:
                        group_src_geoip = dict()
                    group_src_geoip[rule.match] = True
                elif rule.type == RuleType.SRC_PORT:
                    if group_src_port is None:
                        group_src_port = dict()
                    single, ranges = Clash2SingboxTransformer.parse_port_range(rule.match)
                    if len(single) > 0:
                        values = Clash2SingboxTransformer.get_or_default(group_src_port, 'src_port')
                        values.extend(single)
                    if len(ranges) > 0:
                        values = Clash2SingboxTransformer.get_or_default(group_src_port, 'src_port_range')
                        values.extend([f'{r[0]}:{r[1]}' for r in ranges])
                else:
                    field = CLASH2SINGBOX_ALLOWED_RULETYPES[rule.type]
                    if field:
                        obj = group_others.get(rule.type)
                        if obj is None:
                            obj = dict()
                            group_others[rule.type] = obj
                        values = Clash2SingboxTransformer.get_or_default(obj, field)
                        values.append(rule.match)
                    elif rule.type == RuleType.MATCH:
                        if match_rule is not None:
                            print(f'>! multiple match rules found, only the first one is kept, others are skipped')
                        match_rule = rule
                    else:    
                        print(f'>! rule type {rule.type} unimplemented, skipped')
            if group_domain is not None:
                obj = self._gen_rule(group_domain, outbound)
                result.append(obj)
            if group_geosite is not None:
                for geo_key in group_geosite.keys():
                    obj = self._gen_geosite_rule(geo_key, outbound)
                    result.append(obj)
            if group_geoip is not None:
                for geo_key in group_geoip.keys():
                    obj = self._gen_geoip_rule(geo_key, outbound)
                    result.append(obj)
            if group_port is not None:
                obj = self._gen_rule(group_port, outbound)
                result.append(obj)
            if group_src_ip is not None:
                obj = self._gen_rule(group_src_ip, outbound)
                result.append(obj)
            if group_src_geoip is not None:
                for geo_key in group_src_geoip.keys():
                    obj = self._gen_src_geoip_rule(geo_key, outbound)
                    result.append(obj)
            if group_src_port is not None:
                obj = self._gen_rule(group_src_port, outbound)
                result.append(obj)
            for _, rule_obj in group_others.items():
                obj = self._gen_rule(rule_obj, outbound)
                result.append(obj)
        if match_rule is not None:
            self.match_rule_target = match_rule.strategy
        return result
    
    def clear(self):
        self.geoip.clear()
        self.geosite.clear()
        self.match_rule_target = None

    def _ss_transform(self, proxy: dict) -> dict:
        result = {
            'type': 'shadowsocks',
            'tag': proxy['name'],
            'server': proxy['server'],
            'server_port': proxy['port'],
            'method': proxy['cipher'],
            'password': proxy['password'],
        }
        if proxy.get('udp', False) == False:
            result['network'] = 'tcp',
        plugin = proxy.get('plugin')
        if plugin == 'obfs':
            plugin_opts = proxy['plugin-opts']
            result['plugin'] = 'obfs-local'
            result['plugin_opts'] = f'obfs={plugin_opts['mode']};obfs-host={plugin_opts['host']}'
        elif plugin == 'v2ray-plugin':
            plugin_opts = proxy.get['plugin-opts']
            # TODO: v2ray-plugin
            pass
        elif plugin is not None:
            raise NotImplementedError(f"Shadowsocks plugin '{plugin}' is not supported for singbox")
        # TODO: Dial Fields
        return result
    
    def _vmess_transform(self, proxy: dict) -> dict:
        result = {
            'type': 'vmess',
            'tag': proxy['name'],
            'server': proxy['server'],
            'server_port': proxy['port'],
            'uuid': proxy['uuid'],
            'security': proxy.get('cipher', 'auto'),
        }
        alter = proxy.get('alterId')
        if alter is not None:
            if isinstance(alter, str):
                try:
                    result['alter_id'] = int(alter)
                except ValueError:
                    result['alter_id'] = alter
            else:
                result['alter_id'] = alter
        if proxy.get('udp', False) == False:
            result['network'] = 'tcp'
        clash_network = proxy.get('network')
        if clash_network == 'tcp':
            pass
        elif clash_network == 'http':
            http_opts = proxy['http-opts']
            result_transport = {
                'type': 'http',
            }
            servername = proxy.get('servername')
            if servername:
                result_transport['host'] = [servername]
            path = http_opts.get('path')
            if path:
                result_transport['path'] = [path]
            method = http_opts.get('method')
            if method:
                result_transport['method'] = method
            headers = http_opts.get('headers')
            if headers:
                result_transport['headers'] = headers
            result['transport'] = result_transport
        elif clash_network == 'h2':
            h2_opts = proxy['h2-opts']
            result_transport = {
                'type': 'http',
            }
            servername = proxy.get('servername')
            if servername:
                result_transport['host'] = [servername]
            path = h2_opts.get('path')
            if path:
                result_transport['path'] = [path]
            headers = h2_opts.get('headers')
            if headers:
                result_transport['headers'] = headers
            result_transport["idle_timeout"] = "15s",
            result_transport["ping_timeout"] = "15s"
            result['transport'] = result_transport
        elif clash_network == 'grpc':
            grpc_opts = proxy['grpc-opts']
            result_transport = {
                'type': 'grpc',
            }
            grpc_service_name = grpc_opts.get('grpc-service-name')
            if grpc_service_name:
                result_transport['service_name'] = grpc_service_name
            result['transport'] = result_transport
        elif clash_network == 'ws':
            ws_opts = proxy['ws-opts']
            v2ray_http_upgrade = ws_opts.get('v2ray-http-upgrade')
            if not v2ray_http_upgrade:
                result_transport = {
                    'type': 'ws',
                }
                path = ws_opts.get('path')
                if path:
                    result_transport['path'] = [path]
                headers = ws_opts.get('headers')
                if headers:
                    result_transport['headers'] = headers
                max_early_data = ws_opts.get('max-early-data')
                if max_early_data is not None:
                    result_transport['max_early_data'] = max_early_data
                early_data_header_name = ws_opts.get('early-data-header-name')
                if early_data_header_name is not None:
                    result_transport['early_data_header_name'] = early_data_header_name
                result['transport'] = result_transport
            else:
                result_transport = {
                    'type': 'httpupgrade',
                }
                servername = proxy.get('servername')
                if servername:
                    result_transport['host'] = [servername] 
                path = ws_opts.get('path')
                if path:
                    result_transport['path'] = [path]
                headers = ws_opts.get('headers')
                if headers:
                    result_transport['headers'] = headers
                v2ray_http_upgrade_fast_open = ws_opts.get('v2ray-http-upgrade-fast-open')
                if v2ray_http_upgrade_fast_open:
                    raise NotImplementedError("v2ray-http-upgrade-fast-open is not supported in singbox")
                result['transport'] = result_transport
        elif clash_network is not None:
            raise NotImplementedError(f"Vmess network '{clash_network}' is not supported for singbox")
        # TODO: Dial Fields
        return result

    @staticmethod
    def get_or_default(d: Dict[str, List], key: str) -> List:
        values = d.get(key)
        if values is None:
            values = []
            d[key] = values
        return values

    @staticmethod
    def parse_port_range(s: str) -> Tuple[List[int], List[Tuple[int, int]]]:
        ### '114-514/810-1919,65530' -> ([65530], [(114,514),(810,1919)])
        single_ports: List[int] = []
        port_ranges: List[Tuple[int, int]] = []
        parts = []
        # First split by comma
        comma_parts = s.split(',')
        # Then split each part by slash and add to parts list
        for part in comma_parts:
            parts.extend(part.split('/'))
        for part in parts:
            if '-' in part:
                subparts = part.split('-')
                if len(subparts) != 2:
                    raise ValueError(f"Invalid port range: {part}")
                try:
                    start = int(subparts[0])
                    end = int(subparts[1])
                except ValueError:
                    raise ValueError(f"Invalid port range: {part}")
                if start < 0 or start > 65535 or end < 0 or end > 65535 or start > end:
                    raise ValueError(f"Invalid port range: {part}")
                port_ranges.append((start, end))
            else:
                try:
                    port = int(part)
                except ValueError:
                    raise ValueError(f"Invalid port: {part}")
                if port < 0 or port > 65535:
                    raise ValueError(f"Invalid port: {part}")
                single_ports.append(port)
        return single_ports, port_ranges
    

    def _gen_rule(self, d: Dict[str, List], outbound: str) -> dict:
        rule = d
        rule['outbound'] = outbound
        return rule
    
    def _mark_geoip(self, geo_key: str) -> bool:
        if self.geoip.get(geo_key) is None:
            template = SINGBOX_GEOIP_RULESET.get(geo_key)
            if template is None:
                print(f'>! geoip ruleset for {geo_key} not found')
                return False
            ruleset = {
                'tag': f'geoip-{geo_key.lower()}',
            }
            ruleset.update(template)
            self.geoip[geo_key] = ruleset
        return True


    def _mark_geosite(self, geo_key: str) -> bool:
        if self.geosite.get(geo_key) is None:
            template = SINGBOX_GEOSITE_RULESET.get(geo_key)
            if template is None:
                print(f'>! geosite ruleset for {geo_key} not found')
                return False
            ruleset = {
                'tag': f'geosite-{geo_key.lower()}',
            }
            ruleset.update(template)
            self.geosite[geo_key] = ruleset
        return True

    def _gen_geoip_rule(self, geo_key: str, outbound: str) -> dict:
        geo_key = geo_key.upper()
        rule = {
            'rule_set': f'geoip-{geo_key}',
            'outbound': outbound,
        }
        self._mark_geoip(geo_key)
        return rule
    
    def _gen_src_geoip_rule(self, geo_key: str, outbound: str) -> dict:
        geo_key = geo_key.upper()
        rule = {
            'rule_set': f'geoip-{geo_key}',
            'rule_set_ipcidr_match_source': True,
            'outbound': outbound,
        }
        self._mark_geoip(geo_key)
        return rule
    
    def _gen_geosite_rule(self, geo_key: str, outbound: str) -> dict:
        geo_key = geo_key.upper()
        rule = {
            'rule_set': f'geosite-{geo_key}',
            'outbound': outbound,
        }
        self._mark_geosite(geo_key)
        return rule
    

PROXY_PLACEHOLDER = '__PROXY_PLACEHOLDER__'
PROXY_GROUP_PLACEHOLDER = '__PROXY_GROUP_PLACEHOLDER__'
RULE_PLACEHOLDER = '__RULE_PLACEHOLDER__'
RULESET_PLACEHOLDER = '__RULESET_PLACEHOLDER__'

class SingboxConfigWriter(IConfigWriter):

    _transformer: Clash2SingboxTransformer
    _template: Optional[Template]

    def __init__(self):
        super().__init__()
        self._transformer = Clash2SingboxTransformer()
        self._template = None

    def template(self, ifile: BinaryIO) -> None:
        content = ifile.read().decode('utf-8')
        self._template = Template(content)
    
    def write(self, ofile: BinaryIO, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: List[Rule], **kwargs) -> None:
        if self._template is None:
            raise ValueError('template not initialized')
        t = self._transformer
        t.clear()
        content = self._template.render(**kwargs)
        obj = json5_loads(content)
        singbox_proxies = list()
        for p in proxies:
            try:
                sp = t.transform_proxy(p)
                singbox_proxies.append(sp)
            except Exception as e:
                print(f'>! failed to transform proxy {p.name}: {e}')
        singbox_proxy_groups = list()
        for g in proxy_groups:
            try:
                sg = t.transform_proxy_group(g)
                singbox_proxy_groups.append(sg)
            except Exception as e:
                print(f'>! failed to transform proxy group {g.name}: {e}')
        singbox_rules = t.transform_rules(rules)

        template_outbounds: List = obj.get('outbounds')
        template_outbounds = insert_in_list(template_outbounds, lambda x: x == PROXY_PLACEHOLDER, singbox_proxies)
        template_outbounds = insert_in_list(template_outbounds, lambda x: x == PROXY_GROUP_PLACEHOLDER, singbox_proxy_groups)
        obj['outbounds'] = template_outbounds

        template_route: Dict = obj.get('route')
        if template_route is None:
            template_route = dict()
            obj['route'] = template_route
        template_route_rules: List = template_route.get('rules')
        template_route['rules'] = insert_in_list(template_route_rules, lambda x: x == RULE_PLACEHOLDER, singbox_rules)
        
        geo_ruleset = list()
        geo_ruleset.extend(t.geosite.values())
        geo_ruleset.extend(t.geoip.values())
        if len(geo_ruleset) > 0:
            template_route_ruleset: List = template_route.get('rule_set')
            template_route['rule_set'] = insert_in_list(template_route_ruleset, lambda x: x == RULESET_PLACEHOLDER, geo_ruleset)
        if t.match_rule_target is not None:
            template_route['final'] = t.match_rule_target

        w = TextIOWrapper(ofile, 'utf-8')
        json_dump(obj, w, indent=2)
            
        

if __name__ == '__main__':
    from reader_clash import ClashSubscribeReader
    s = r"D:\Storage\Softwares\Mihomo\cache\FlowerCloud.yml"
    so = r"D:\Storage\Softwares\Mihomo\cache\FlowerCloud-singbox.json"
    reader = ClashSubscribeReader()
    with open(s, 'rb') as ifile:
        reader.read(ifile, True)
    t = Clash2SingboxTransformer()
    clash_proxies = reader.get_proxies()
    singbox_proxies = list()
    for p in clash_proxies:
        try:
            sp = t.transform_proxy(p)
            singbox_proxies.append(sp)
        except Exception as e:
            print(f'>! failed to transform proxy {p.name}: {e}')
    clash_proxy_groups = reader.get_proxy_groups()
    singbox_proxy_groups = list()
    for g in clash_proxy_groups:
        try:
            sg = t.transform_proxy_group(g)
            singbox_proxy_groups.append(sg)
        except Exception as e:
            print(f'>! failed to transform proxy group {g.name}: {e}')
    clash_rules = reader.get_rules()
    singbox_rules = t.transform_rules(clash_rules)
    out = {
        'proxies': singbox_proxies,
        'proxy-groups': singbox_proxy_groups,
        'rules': singbox_rules,
        'geoip': list(t.geoip.values()),
        'geosite': list(t.geosite.values()),
    }
    with open(so, 'w', encoding='utf-8') as ofile:
        import json
        json.dump(out, ofile, indent=4)
    pass