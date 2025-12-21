from abc import ABC, abstractmethod
from argparse import _SubParsersAction, ArgumentParser, Namespace
from os import path
from typing import Dict
import logging

from ..config import Configuration

logger = logging.getLogger(__name__)

class Installer(ABC):

    @abstractmethod
    def install(self, cfg: Dict, location: str, **kwargs):
        pass

    @abstractmethod
    def uninstall(self, cfg: Dict):
        pass


class Context(ABC):

    @abstractmethod
    def get_installer(self, ty: str) -> Installer:
        pass

    @abstractmethod
    def get_install_dir(self) -> str:
        pass

    @abstractmethod
    def get_assets_dir(self) -> str:
        pass

    @abstractmethod
    def get_config(self) -> Configuration:
        pass


def cmd_install(args: Namespace, ctx: Context):
    cfg = ctx.get_config()
    
    ty: str = args.type
    if not ty:
        return

    location: str = args.location
    if not location:
        location = ctx.get_install_dir()

    cfg_key = f'install.{ty}'
    cfg_data: Dict = None
    try:
        installer = ctx.get_installer(ty)
        assets_root = path.join(ctx.get_assets_dir(), 'install')
        cfg_data = cfg.get(cfg_key)
        if not cfg_data:
            cfg_data = {}
        installer.install(cfg_data, location, assets_root=assets_root, cfg_file=path.abspath(cfg.file))
    except Exception as e:
        logger.error(f"Installation failed for type {ty}: {e}")
    finally:
        if cfg_data is not None:
            cfg.set(cfg_key, cfg_data)
            cfg.save()



def cmd_uninstall(args: Namespace, ctx: Context):
    cfg = ctx.get_config()

    ty: str = args.type
    if not ty:
        return
        
    cfg_key = f'installer.{ty}'
    cfg_data: Dict = None
    try:
        cfg_data = cfg.get(cfg_key)
        if not cfg_data:
            logger.warning(f"No configuration found for installer type {ty}. Nothing to uninstall.")
            return
        installer = ctx.get_installer(ty)
        installer.uninstall(cfg_data)
    except Exception as e:
        logger.error(f"Uninstallation failed for type {ty}: {e}")
    finally:
        if cfg_data is not None:
            cfg.set(cfg_key, None)
            cfg.save()
    pass

def register_install_commands(subparsers: _SubParsersAction):
    
    install_parser = subparsers.add_parser('install', help='Install a tool')
    install_parser.add_argument('type', type=str, help='Type of tool to install')
    install_parser.add_argument('--location', type=str, help='Installation location')
    install_parser.set_defaults(func=cmd_install)

    uninstall_parser = subparsers.add_parser('uninstall', help='Uninstall a tool')
    uninstall_parser.add_argument('type', type=str, help='Type of tool to uninstall')
    uninstall_parser.set_defaults(func=cmd_uninstall)