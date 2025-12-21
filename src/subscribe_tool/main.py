import logging
from argparse import ArgumentParser
from os import path
from typing import Callable, override
from pathlib import Path
from json import dumps

from .config import Configuration
from .reader import ISubscribeReader
from .writer import IConfigWriter
from .subscribe import ProviderManager, register_subscribe_commands, Context as ContextA
from .install import Installer, register_install_commands, Context as ContextB
from .dynload import DynamicLoad

logger = logging.getLogger(__name__)


__CACHED_PACKAGE_ROOT: Path = None

def get_package_root() -> Path:
    global __CACHED_PACKAGE_ROOT
    if __CACHED_PACKAGE_ROOT is None:
        p = Path(path.dirname(path.abspath(__file__)))
        __CACHED_PACKAGE_ROOT = p.parent.parent
    return __CACHED_PACKAGE_ROOT

def setup_logging(log_level=logging.INFO):
    """Configure logging for the application."""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Reader and Writer mappings
READER_CLASSES = {
    'clash': '.reader.reader_clash:ClashSubscribeReader',
    'v2ray': '.reader.reader_subs:SubscribeReaderSimple',
}

WRITER_CLASSES = {
    'clash': '.writer.writer_clash:ClashConfigWriter',
    'singbox': '.writer.writer_singbox:SingboxConfigWriter',
}

INSTALLER_CLASSES = {
    'clash': '.install.install_clash:ClashInstaller',
}

class Application(ContextA, ContextB):

    _root: str
    _cfg: Configuration
    _dynamic_load: DynamicLoad
    _reader_factory: Callable[[str], ISubscribeReader]
    _provider_manager: ProviderManager

    def __init__(self, root: str, config_file: str):
        super().__init__()
        self._root = root
        self._cfg = Configuration(config_file)
        self._dynamic_load = DynamicLoad(__package__)
        self._reader_factory = lambda ty: self._get_reader(ty)
        self._provider_manager = ProviderManager()
        self._cfg.register_handler('provider_manager', self._provider_manager)
        self._cfg.load()
    
    @override
    def get_provider_manager(self) -> ProviderManager:
        return self._provider_manager

    @override
    def get_reader(self, ty: str) -> ISubscribeReader:
        class_path = READER_CLASSES.get(ty)
        if class_path is None:
            raise ValueError(f'Unknown reader type: {ty}')
        return self._dynamic_load.get(class_path, ISubscribeReader)
    
    @override
    def get_writer(self, ty: str) -> IConfigWriter:
        class_path = WRITER_CLASSES.get(ty)
        if class_path is None:
            raise ValueError(f'Unknown writer type: {ty}')
        return self._dynamic_load.get(class_path, IConfigWriter)
    
    @override
    def get_cache_dir(self) -> str:
        p = self._cfg.get('env.cache')
        if not p:
            p = path.join(self._root, 'var', 'cache')
            p = path.abspath(p)
            self._cfg.set('env.cache', p)
        return p
    
    @override
    def get_installer(self, ty: str) -> Installer:
        class_path = INSTALLER_CLASSES.get(ty)
        if class_path is None:
            raise ValueError(f'Unknown installer type: {ty}')
        return self._dynamic_load.get(class_path, Installer)
    
    @override
    def get_install_dir(self) -> str:
        p = self._cfg.get('env.install')
        if not p:
            p = path.join(self._root, 'var', 'run')
            p = path.abspath(p)
            self._cfg.set('env.install', p)
        return p
    
    @override
    def get_assets_dir(self) -> str:
        package_root = get_package_root()
        assets_dir = package_root / 'assets'
        return str(assets_dir)

    @override
    def get_config(self) -> Configuration:
        return self._cfg

def main():
    setup_logging(logging.INFO)
    root = path.curdir
    config_path = path.join(root, 'var', 'subscribe-tool.json')
    config_path = path.abspath(config_path)
    p = ArgumentParser(
        prog='subscribe-tool',
        description='a simple subscribe tool'
    )
    p.add_argument('--config', '-c', dest='config', nargs='?', default=config_path, help='Config file path (default: var/subscribe-tool.json)')   
    subparsers = p.add_subparsers(dest='command', help='Available commands')
    register_subscribe_commands(subparsers)
    register_install_commands(subparsers)
    subparser = subparsers.add_parser('env', help='Show environment information')

    args = p.parse_args()
    if args.command == 'env':
        print()
        print(f'Root directory: {root}')
        print(f'Package directory: {get_package_root()}')
        print(f'Config file: {args.config}')
        print()
        print('Environment Variables:')
        config = Configuration(args.config)
        config.load()
        env = config.get('env')
        if not env:
            print('  (no environment variables configured)')
        else:
            print(dumps(env, indent=4))
    elif not hasattr(args, 'func'):
        p.print_help()
    else:
        try:
            app = Application(root, args.config)
            args.func(args, app)
        except Exception as e:
            logger.error(f'Error: {e}')
            exit(1)
    pass


if __name__ == '__main__':
    main()