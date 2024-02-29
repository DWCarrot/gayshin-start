from io import BufferedIOBase, BytesIO, TextIOWrapper
from typing import Dict, List
from data import ISubscribeReader, Proxy, ProxyGroup, Rule
from base64 import b64decode
from json import load as json_load, dump as json_dump

HEADER = b'vmess://'

def record_cvt_v2(record: dict):
    proxy = {
        'type': 'vmess',
        'name': record['ps'],
        'server': record['add'],
        'port': record['port'],
        'uuid': record['id'],
        'alterId': record.get('aid', 0),
        'cipher': record.get('scy', 'auto'),
        'udp': True,
        'servername': record.get('sni'),
        'network': record['net'],
        'tls': record.get('tls') == 'tls',
        'skip-cert-verify': False
    }
    if proxy['network'] == 'ws':
        proxy['ws-opts'] = {
            'path': record['path'],
            'headers': {
                'Host': record['host'],
            }
        }
        proxy['ws-path'] = proxy['ws-opts']['path']
        proxy['ws-headers'] = proxy['ws-opts']['headers']
    return proxy


class VmessSubscribeReaderSimple(ISubscribeReader):

    inner: List[Dict]

    def __init__(self):
        super().__init__()

    def get_cache_name(self, filename: str) -> str:
        return filename + '.json'

    def read(self, ifile: BufferedIOBase, is_cache: bool, ofile_cache: BufferedIOBase | None = None) -> None:
        if not is_cache:
            raw = ifile.read()
            data = b64decode(raw)
            self.inner = list()
            for record_line in data.splitlines():
                if not record_line.startswith(HEADER):
                    continue
                record_line = record_line[len(HEADER):]
                record_raw = b64decode(record_line)
                record = json_load(BytesIO(record_raw))
                self.inner.append(record)
            if ofile_cache is not None:
                writer = TextIOWrapper(ofile_cache, encoding='utf-8')
                json_dump(self.inner, writer, indent=4)
                writer.flush()
        else:
            self.inner = json_load(ifile)

    def get_proxies(self) -> List[Proxy]:
        proxies = list()
        for record in self.inner:
            if record.get('v') == '2':
                proxy = record_cvt_v2(record)
                proxies.append(Proxy(proxy))
        return proxies
    
    def get_all_proxies(self, name: str) -> ProxyGroup:
        inner = {
            'name': name,
            'type': 'select',
            'proxies': [p['ps'] for p in self.inner]
        }
        return ProxyGroup(inner)

    def get_proxy_groups(self) -> List[ProxyGroup]:
        return []

    def get_rules(self, name: str) -> List[Rule]:
        return []