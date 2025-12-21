from abc import ABC, abstractmethod
from collections import OrderedDict
import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ConfigurationHandler(ABC):

    @abstractmethod
    def on_load(self, data: Dict):
        pass

    @abstractmethod
    def on_save(self, data: Dict):
        pass

    @abstractmethod
    def on_enable(self, ctx: "Configuration"):
        pass

    @abstractmethod
    def on_disable(self, ctx: "Configuration"):
        pass


class Configuration(object):

    _file: str
    _data: Dict
    _handlers: OrderedDict[str, ConfigurationHandler]

    def __init__(self, file: str):
        self._file = file
        self._data = None
        self._handlers = OrderedDict()

    @property
    def file(self) -> str:
        return self._file

    def register_handler(self, name: str, handler: ConfigurationHandler):
        self._handlers[name] = handler
        handler.on_enable(self)

    def unregister_handler(self, name: str):
        handler = self._handlers.get(name)
        if handler is not None:
            handler.on_disable(self)
            del self._handlers[name]

    def load(self):
        try:
            with open(self._file, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = {}
        except Exception as e:
            logger.error(f'Failed to load configuration file: {e}')
            self._data = {}

        for handler in self._handlers.values():
            try:
                handler.on_load(self._data)
            except Exception as e:
                logger.error(f'Error in on_load of handler {handler}: {e}')

    def save(self):
        for handler in self._handlers.values():
            try:
                handler.on_save(self._data)
            except Exception as e:
                logger.error(f'Error in on_save of handler {handler}: {e}')

        try:
            with open(self._file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Failed to save configuration file: {e}')

    def get(self, key: str) -> Any:
        _tmp = self._data
        for part in key.split('.'):
            if not isinstance(_tmp, dict):
                return None
            _tmp = _tmp.get(part)
            if _tmp is None:
                return None
        return _tmp
    
    def set(self, key: str, value: Any):
        _tmp = self._data
        parts = key.split('.')
        for part in parts[:-1]:
            if part not in _tmp or not isinstance(_tmp[part], dict):
                _tmp[part] = {}
            _tmp = _tmp[part]
        _tmp[parts[-1]] = value
