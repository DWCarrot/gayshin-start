from io import BufferedIOBase, BytesIO, TextIOWrapper
from typing import Dict, List, Optional
from urllib.parse import parse_qs, unquote_plus, urlparse
from data import ISubscribeReader, Proxy, ProxyGroup, Rule
from base64 import b64decode
from json import load as json_load, dump as json_dump

HEADER_VMESS = b'vmess://'

def record_cvt_v2(url: str):
    pos = len(HEADER_VMESS)
    data = b64decode(url[pos:])
    record = json_load(BytesIO(data))
    version = int(record['v'])

    proxy = {
        'type': 'vmess',
        'name': str(record['ps']),
        'server': str(record['add']),
        'port': int(record['port']),
        'uuid': str(record['id']),
        'alterId': int(record.get('aid', 0)),
        'cipher': str(record.get('scy', 'auto')),
        #'udp': True,
        'network': str(record['net']),
        'tls': record.get('tls') == 'tls',
        #'skip-cert-verify': False
    }
    sni = record.get('sni')
    if sni:
        proxy['servername'] = sni

    host = record.get('host')
    path = record.get('path')
    if version == 1:
        if host:
            host, path = host.split(';', 1)
    elif version == 2:
        path = record.get('path')
    else:
        raise ValueError(f'Unsupported vmess version: {version}')
    network = proxy['network']
    if network == 'tcp':
        pass
    elif network == 'grpc':
        proxy['grpc-opts'] = {
            'grpc-service-name': path,
        }
    elif network == 'ws':
        proxy['ws-opts'] = {
            'path': record['path'],
            'headers': {
                'Host': record['host'],
            }
        }
    return proxy

def record_cvt_ss(url: str):
    _name: Optional[str] = None
    _group: Optional[str] = None
    _server: Optional[str] = None
    _port: Optional[int] = None
    _method: Optional[str] = None
    _password: Optional[str] = None
    _plugin: Optional[str] = None
    _plugin_opts: Optional[Dict] = None
    url = urlparse(url)
    if url.fragment:
        _name = unquote_plus(url.fragment)
    if url.query:
        query_params = parse_qs(url.query)
        plugin_part = query_params.get('plugin')
        if plugin_part and len(plugin_part) > 0:
            plugin_part = plugin_part[0]
            parts = plugin_part.split(';')
            _plugin = parts[0]
            _plugin_opts = dict()
            for part in parts[1:]:
                if '=' in part:
                    k, v = part.split('=', 1)
                    _plugin_opts[k] = v
                else:
                    _plugin_opts[part] = True
            if not len(_plugin_opts) > 0:
                _plugin_opts = None
        group_part = query_params.get('group')
        if group_part and len(group_part) > 0:
            _group = b64decode(group_part[0]).decode('utf-8')
    if url.username:
        secret = b64decode(url.username).decode('utf-8')
        _method, _password = secret.split(':', 1)
        _server = url.hostname
        _port = url.port
    else:
        decoded = b64decode(url.netloc).decode('utf-8')
        # method:password@server:port
        pos = decoded.index('@')
        pos2 = decoded.rindex(':')
        pos1 = decoded.index(':', end=pos)
        _method = decoded[:pos1]
        _password = decoded[pos1+1:pos]
        _server = decoded[pos+1:pos2]
        _port = int(decoded[pos2+1:])
    proxy = {
        'type': 'ss',
        'name': _name,
        'server': _server,
        'port': _port,
        'cipher': _method,
        'password': _password,
    }
    if _plugin:
        proxy['plugin'] = _plugin
        if _plugin_opts:
            proxy['plugin-opts'] = _plugin_opts
    return proxy

class VmessSubscribeReaderSimple(ISubscribeReader):

    inner: List[Dict]

    def __init__(self):
        super().__init__()

    def get_cache_name(self, filename: str) -> str:
        return filename + '.txt'

    def read(self, ifile: BufferedIOBase, is_cache: bool, ofile_cache: BufferedIOBase | None = None) -> None:
        links: List[str] = list()
        if not is_cache:
            raw = ifile.read()
            data = b64decode(raw)
            for record_line in data.splitlines():
                links.append(record_line.decode('utf-8').strip())
            if ofile_cache is not None:
                writer = TextIOWrapper(ofile_cache, encoding='utf-8')
                writer.writelines(link + '\n' for link in links)
                writer.flush()
        else:
            for line in ifile:
                line = line.rstrip(b'\n\r')
                if line:
                    links.append(line.decode('utf-8'))
        self.inner = list()
        for link in links:
            if link.startswith('vmess://'):
                record = record_cvt_v2(link)
                self.inner.append(record)
            elif link.startswith('ss://'):
                record = record_cvt_ss(link)
                self.inner.append(record)
            else:
                print(f'Unsupported link: {link}')


    def get_proxies(self) -> List[Proxy]:
        proxies = [Proxy(p) for p in self.inner]
        return proxies
    
    def get_all_proxies(self, name: str) -> ProxyGroup:
        inner = {
            'name': name,
            'type': 'select',
            'proxies': [p['name'] for p in self.inner]
        }
        return ProxyGroup(inner)

    def get_proxy_groups(self) -> List[ProxyGroup]:
        return []

    def get_rules(self, name: str) -> List[Rule]:
        return []