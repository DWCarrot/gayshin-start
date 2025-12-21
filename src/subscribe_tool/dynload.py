import importlib
from typing import Any, Dict, Optional, Tuple, Type


class DynamicLoad:
    """Generic dynamic loader that loads classes on-demand without registration."""

    _package: Optional[str]
    _modules: Dict[str, Any]
    _constructors: Dict[str, Type]  # Cache for loaded constructors

    def __init__(self, package: Optional[str] = None):
        self._package = package
        self._modules = dict()
        self._constructors = dict()

    def get(self, key: str, interface: Type) -> Any:
        """
        Load and instantiate a class on-demand.
        
        Args:
            class_path: Full class path in format 'module.path:ClassName'
                       e.g., 'subscribe_tool.reader.reader_clash:ClashSubscribeReader'
            interface: The interface type the class should implement
            
        Returns:
            Instance of the class
            
        Raises:
            ValueError: If class_path format is invalid
            ModuleNotFoundError: If module cannot be imported
            AttributeError: If class not found in module
            TypeError: If class does not implement the interface
        """
        # Check cache first
        klass = self._constructors.get(key)
        if klass is not None:
            if not issubclass(klass, interface):
                raise TypeError(f'Class {klass.__name__} does not implement {interface.__name__}')
            return klass()
        
        module_name, class_name = self.extract_key(key)
        
        # Load module
        module = self._modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name, self._package)
            self._modules[module_name] = module
    
        klass = getattr(module, class_name)
        
        # Verify it implements the interface
        if not issubclass(klass, interface):
            raise TypeError(f'Class {class_name} does not implement {interface.__name__}')
        
        # Cache the constructor and return instance
        self._constructors[key] = klass
        return klass()
    
    @staticmethod
    def extract_key(key: str) -> Tuple[str, str]:
        """Extract module and class name from class path."""
        tuple = key.rsplit(':', 1)
        if len(tuple) != 2:
            raise ValueError(f'Invalid class_path format. Expected "module.path:ClassName", got "{key}"')
        return tuple[0], tuple[1]