from typing import BinaryIO, Dict, List, Optional
from data import IConfigWriter, Proxy, ProxyGroup, Rule
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    print('[warning] unable to load libyaml; use python module instead', e)
    from yaml import Loader, Dumper
from jinja2 import Template

from utils import insert_in_list

PROXY_PLACEHOLDER = '__PROXY_PLACEHOLDER__'
PROXY_GROUP_PLACEHOLDER = '__PROXY_GROUP_PLACEHOLDER__'
RULE_PLACEHOLDER = '__RULE_PLACEHOLDER__'

class ClashConfigWriter(IConfigWriter):

    _template: Optional[Template]

    def __init__(self):
        super().__init__()
        self._template = None

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



# __main__
#
# args[0]:      template file name
# args[1..n]:   variables "<name>:<type>=<value>"; type in bool,int,float,str,null
#                   enable_tun:bool=true
#                   port:int=10000
#                   qb:null=
#
# example:
#   python writer_clash.py config.template.yaml "enable_tun:bool=true" "port:int=10086"
#

if __name__ == '__main__':
    from sys import argv
    from io import StringIO

    args = argv[1:]
    if len(args) < 1:
        exit()
    ifile_name = args[0]
    variables = dict()
    args = args[1:]
    TYPE_MAP = {
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "null": None
    }
    for i, arg in enumerate(args):
        sp = arg.find('=')
        if sp < 0:
            args = args[i:]
            break
        sp0 = arg.index(':', 0, sp)
        _name = arg[:sp0]
        _type = arg[sp0+1:sp]
        _value = arg[sp+1:]
        _type = TYPE_MAP.get(_type)
        if _type is None:
            _value = None
        else:
            _value = _type(_value)
        variables[_name] = _value
    print('variables:', variables)

    
    writer = ClashConfigWriter()
    with open(ifile_name, 'r', encoding='utf-8') as ifile:
        writer.template(ifile)
    
    s = StringIO()
    writer.write(s, [], [], {}, **variables)
    print(s.getvalue())
        