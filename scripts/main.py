from argparse import Action, ArgumentParser
from io import BytesIO, TextIOWrapper
from os import makedirs, path
from typing import Dict, Tuple
from typing import Dict
from io import TextIOWrapper
from data import GeneralGroup, ISubscribeReader, IConfigWriter, Info, merge
from json import load as json_load, dump as json_dump

from utils import DynamicLoad, download_config


class SubscribeItem:

    name: str
    priority: int
    type: str
    url: str
    file: str
    use_rules: bool
    general_group: Dict[str, GeneralGroup]
    ignore: bool

    def __init__(self, raw: Dict):
        self.name = raw['name']
        self.priority = raw['priority']
        self.type = raw['type']
        self.url = raw.get('url', '')
        self.file = raw.get('file', '')
        self.use_rules = raw.get('use_rules', False)
        self.update_interval = raw.get('update_interval', 0)
        self.general_group = {}
        for key in GeneralGroup:
            value = raw.get(key.name)
            if value:
                self.general_group[value] = key
        self.ignore = raw.get('ignore', False)
        pass

    def load(self, cache_dir: str, dl: DynamicLoad, timeout: int = 5000, no_update: bool = False, cache_index: Dict[str, str] = None) -> Info:
        reader = None
        if self.url and not no_update:
            print(f'># downloading {self.url} for {self.name} ...')
            try:
                raw, filename = download_config(self.url)
                with BytesIO(raw) as ifile:
                    reader = dl.get_reader(self.type)
                    filename = reader.get_cache_name(self._get_valid_filename(filename))
                    print(f'># downloaded {self.url} as {filename}')
                    filepath = path.join(cache_dir, filename)
                    with open(filepath, 'wb') as ofile_cache:
                        reader.read(ifile, False, ofile_cache)
                    if cache_index is not None:
                        cache_index[self.name] = filepath
                    print(f'># saved file {filepath}')
            except Exception as e:
                print(f'>! failed with remote {self.name}', e)
                reader = None
        
        if reader is None:
            if self.file:
                print(f'># load file {self.file} for {self.name}')
                try:
                    with open(self.file, 'rb') as ifile:
                        reader = dl.get_reader(self.type)
                        reader.read(ifile, False, None)
                except Exception as e:
                    print(f'>! failed with local {self.name}', e)
                    reader = None
            else:
                if cache_index is not None:
                    filepath = cache_index.get(self.name)
                    if filepath:
                        print(f'># load cache {filepath} for {self.name}')
                        try:
                            with open(filepath, 'rb') as ifile:
                                reader = dl.get_reader(self.type)
                                reader.read(ifile, True, None)
                        except Exception as e:
                            print(f'>! failed with cache {self.name}', e)
                            reader = None
        if reader is None:
            return None
        return Info(reader, self.name, self.priority, self.use_rules, self.general_group)

    def __repr__(self) -> str:
        return f"SubscribeItem(name={self.name}, priority={self.priority}, type={self.type}, url={self.url}, file={self.file}, use_rules={self.use_rules}, general_group={self.general_group})"  

    def _get_valid_filename(self, network_filename: str | None) -> str:
        return self.name #TODO implement this

class VariableAction(Action):

    @staticmethod
    def _parse_bool(s: str):
        if s.lower() == 'true' or s == '1':
            return True
        elif s.lower() == 'false' or s == '0':
            return False
        raise ValueError('invalid bool value; expect true or false')

    TYPE_MAP = {
        "bool": _parse_bool,
        "int": int,
        "float": float,
        "str": str,
        "null": lambda s: None
    }

    def __call__(self, parser, namespace, values, option_string=None):
        variables = getattr(namespace, self.dest)
        if variables is None:
            variables = {}
        try:
            _name, _value = self._parse_varible(values)
            variables[_name] = _value
        finally:
            setattr(namespace, self.dest, variables)

    @staticmethod
    def _parse_varible(value: str) -> Tuple[str, any]:
        # <name>:<type>=<value>
        value_sp = value.find('=')
        name_sp = value.find(':', 0, value_sp if value_sp > 0 else len(value))
        if name_sp < 0:
            if value_sp < 0:
                raise ValueError('invalid variable format; expect <name>:<type>=<value>')
            _name = value[:value_sp]
            _type = 'str'
        else:
            _name = value[:name_sp]
            if value_sp < 0:
                _type = value[name_sp+1:]
                if not _type == 'null':
                    raise ValueError('invalid variable format; expect <name>:<type>=<value>')
            else:
                _type = value[name_sp+1:value_sp]
        _type = VariableAction.TYPE_MAP[_type]
        _value = _type(value[value_sp+1:])
        return _name, _value

if __name__ == '__main__':
    
    root = path.curdir
    p = ArgumentParser(
        prog='clash-subscribe-tool',
        description='a simple subscribe tool for clash-core'
    )
    p.add_argument('--timeout', type=int, dest='timeout', default=10000)
    p.add_argument('-s', '--cache', dest='cache', default=path.join(root, 'cache'))
    p.add_argument('-T', '--template', dest='template', default=path.join(root, 'config.template.yaml'))
    p.add_argument('-K', '--target-type', dest='target_type', default='clash')
    p.add_argument('-o', '--output', dest='output', default=path.join(root, 'config.yaml'))
    p.add_argument('-D', '--variable', dest='variables', action=VariableAction, default={})
    p.add_argument('-l', '--no-update', dest='no_update', action='store_true', default=False)
    p.add_argument('subs_file', default=path.join(root, 'subscribe.json'), nargs='?')
    args = p.parse_args()
    args.cache = path.abspath(args.cache)
    args.template = path.abspath(args.template)
    args.output = path.abspath(args.output)
    args.subs_file = path.abspath(args.subs_file)
    print(args)

    if not path.exists(args.cache):
        makedirs(args.cache, exist_ok=True)
    
    sub_items = []
    with open(args.subs_file, 'r', encoding='utf-8') as ifile_subs:
        sub_items = json_load(ifile_subs)
        sub_items = [SubscribeItem(item) for item in sub_items]
    cache_index = {}
    cache_index_path = path.join(args.cache, 'cache.json')
    try:
        with open(cache_index_path, 'r', encoding='utf-8') as ifile_cache_index:
            cache_index = json_load(ifile_cache_index)
    except FileNotFoundError as e:
        pass
    except Exception as e:
        print(f'>! failed to load cache index', e)

    print('')
    for item in sub_items:
        print(item)

    dl = DynamicLoad()
    dl.register_reader('clash', 'reader_clash:ClashSubscribeReader')
    dl.register_reader('subscribe', 'reader_subs:SubscribeReaderSimple')
    dl.register_writer('clash', 'writer_clash:ClashConfigWriter')
    dl.register_writer('singbox', 'writer_singbox:SingboxConfigWriter')

    data = []
    for item in sub_items:
        if item.ignore:
            continue
        print('')
        info = item.load(args.cache, dl, args.timeout, args.no_update, cache_index)
        if info is None:
            continue
        print(f"># modify {item.name}")
        info.modify_by_name(item.name)
        data.append(info)

    try:
        with open(cache_index_path, 'w', encoding='utf-8') as ofile_cache_index:
            json_dump(cache_index, ofile_cache_index, indent=4)
    except Exception as e:
        print(f'>! failed to save cache index', e)

    del sub_items

    print('')
    ROOT = ''
    proxies, proxy_groups, rules = merge(data)
    print(f'># merged into: proxies[{len(proxies)}], proxy_groups[{len(proxy_groups)}], rules[{len(rules)}]')

    print('')
    writer = dl.get_writer(args.target_type)
    print(f'># writer: {args.target_type}')
    with open(args.template, 'rb') as ifile_template:
        writer.template(ifile_template)
        print(f'># template loaded from {args.template}')
    with open(args.output, 'wb') as ofile:
        writer.write(ofile, proxies, proxy_groups, rules, **args.variables)
        print(f'># config written to {args.output}')

    pass
