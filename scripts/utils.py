from collections.abc import Iterable
import importlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from urllib import request

from data import IConfigWriter, ISubscribeReader

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36 Edg/103.0.1264.62'

def download_config(url: str, timeout: int = 5000) -> Tuple[bytes, Optional[str]]:
    filename: str | None = None
    req = request.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    resp = request.urlopen(req, timeout=timeout/1000.0)
    content_disposition = [p.strip() for p in resp.getheader('Content-Disposition', default='').split(';')]
    if len(content_disposition) >= 2 and content_disposition[0] == "attachment":
        for kv in content_disposition[1:]:
            q = kv.split('=', 1)
            if len(q) == 2 and q[0] == 'filename':
                filename = q[1]
                break
    raw = resp.read()
    return raw, filename



class DynamicLoad:

    _modules: Dict[str, Any]
    _readers: Dict[str, Union[str, ISubscribeReader]]
    _writers: Dict[str, Union[str, IConfigWriter]]

    def __init__(self):
        self._modules = dict()
        self._readers = dict()
        self._writers = dict()

    def register_reader(self, type: str, class_path: str):
        self._readers[type] = class_path

    def register_writer(self, name: str, class_path: str):
        self._writers[name] = class_path

    def _load_klass(self, class_path: str, ty: Type) -> Type:
        module_name, class_name = class_path.split(':', 2)
        module = self._modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
            self._modules[module_name] = module
        klass = getattr(module, class_name)
        if not issubclass(klass, ty):
            raise TypeError(f'Class {class_name} is not a subclass of {ty.__name__}')
        return klass

    def get_reader(self, type: str) -> ISubscribeReader:
        reader_class = self._readers.get(type)
        if reader_class is None:
            return None
        if isinstance(reader_class, str):
            reader_class = self._load_klass(reader_class, ISubscribeReader)
            self._readers[type] = reader_class
        return reader_class()
    
    def get_writer(self, name: str) -> IConfigWriter:
        writer_class = self._writers.get(name)
        if writer_class is None:
            return None
        if isinstance(writer_class, str):
            writer_class = self._load_klass(writer_class, IConfigWriter)
            self._writers[name] = writer_class
        return writer_class()
    

def insert_in_list(original: Optional[List[Any]], locate: Callable[[Any], bool], items: Iterable[Any]) -> List[Any]:
    if not original or len(original) == 0:
        return list(items)
    result: List[Any] = []
    inserted = False
    for v in original:
        if locate(v):
            if inserted:
                raise ValueError('multiple insert location match found')
            inserted = True
            for item in items:
                result.append(item)
        else:
            result.append(v)
    if not inserted:
        for item in items:
            result.append(item)
    return result