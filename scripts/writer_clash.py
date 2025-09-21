from io import BufferedIOBase, BytesIO, StringIO
from typing import Dict, List
from data import IConfigWriter, Proxy, ProxyGroup, Rule
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    print('[warning] unable to load libyaml; use python module instead', e)
    from yaml import Loader, Dumper


def _variable_constructor(loader, node):
    key = loader.construct_python_str(node)
    if key.startswith('$'):
        _key = key[1:]
        _type = None
        _default = None
        if _key.startswith('{'):
            sp = _key.find('}')
            if sp < 0:
                return key
            _rest = _key[sp+1:]
            _key = _key[1:sp]
            sp = _key.find(':')
            if sp > 0:
                _type = _key[sp+1:]
                _key = _key[:sp]
            if _rest.startswith('='):
                _default = _rest[1:]
                if _type is None:
                    _type = 'str'
        if _type == 'bool':
            if _default == '1' or _default.lower() == 'true':
                _default = True
            elif _default == '0' or _default.lower() == 'false':
                _default = False
            else:
                _default = None
            _type = bool
        elif _type == 'int':
            try:
                _default = int(_default)
            except:
                _default = None
            _type = int
        elif _type == 'float':
            try:
                _default = float(_default)
            except:
                _default = None
            _type = float
        elif _type == 'str':
            _type = str
        
        _variables = loader.__patch__variables
        value = _variables.get(_key)
        if value is None or (_type is not None and not isinstance(value, _type)):
            value = _default
            return value
        return value
    return key


class ClashConfigWriter(IConfigWriter):

    _template: bytes

    def __init__(self):
        super().__init__()
        self._template = None
        Loader.add_constructor('!var', _variable_constructor)

    def template(self, ifile: BufferedIOBase) -> None:
        self._template = ifile.read()

    def write(self, ofile: BufferedIOBase, proxies: List[Proxy], proxy_groups: List[ProxyGroup], rules: Dict[str, List[Rule]], **kwargs) -> None:
        loader = Loader(BytesIO(self._template))
        setattr(loader, '__patch__variables', kwargs)
        template = None
        try:
            template = loader.get_single_data()
        finally:
            loader.dispose()
        template_proxies = template.get('proxies')
        if template_proxies is None:
            template_proxies = []
            template['proxies'] = template_proxies
        for p in proxies:
            template_proxies.append(p.inner)
        template_proxy_groups = template.get('proxy-groups')
        if template_proxy_groups is None:
            template_proxy_groups = []
            template['proxy-groups'] = template_proxy_groups
        for g in proxy_groups:
            template_proxy_groups.append(g.inner)
        template_rules = template.get('rules')
        if template_rules is None:
            template_rules = []
            template['rules'] = template_rules
        template_sub_rules = template.get('sub-rules')
        for (key, v_rules) in rules.items():
            if not key:
                for r in v_rules:
                    template_rules.append(r.raw)
            else:
                if template_sub_rules is None:
                    template_sub_rules = dict()
                    template['sub-rules'] = template_sub_rules
                template_sub_rules[key] = [r.raw for r in v_rules]
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
        