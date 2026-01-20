from abc import ABC, abstractmethod
from collections import OrderedDict
import logging
from os import path
from typing import Dict, List, Optional, Tuple, override
from argparse import _SubParsersAction, Action, ArgumentParser, Namespace

from .config import Configuration, ConfigurationHandler
from .reader import ISubscribeReader
from .writer import IConfigWriter
from .provider import Provider, ProcessSettings, extract, merge

logger = logging.getLogger(__name__)


class ProviderManager(ConfigurationHandler):
    """Manages providers"""
    
    _providers: OrderedDict[str, Provider]
    _last_cmd: Dict
    _ctx: Configuration

    def __init__(self):
        self._providers = OrderedDict()
        self._ctx = None
        self._last_cmd = None

    @override
    def on_enable(self, ctx: Configuration):
        """Enable provider manager with configuration context"""
        self._ctx = ctx

    @override
    def on_disable(self, ctx: Configuration):
        """Disable provider manager with configuration context"""
        self._ctx = None

    @override
    def on_load(self, data: Dict):
        """Load providers from configuration data"""
        providers_raw = data.get('providers')
        if providers_raw and isinstance(providers_raw, list):
            for provider_raw in providers_raw:
                try:
                    provider = Provider(**provider_raw)
                    self._providers[provider.name] = provider
                except Exception as e:
                    logger.warning('Failed to deserialize provider: %s', e)
        last_cmd = data.get('generate')
        if last_cmd and isinstance(last_cmd, dict):
            self._last_cmd = last_cmd
    
    @override
    def on_save(self, data: Dict):
        """Save providers to configuration data"""
        data['providers'] = [provider.serialize() for provider in self._providers.values()]
        if self._last_cmd:
            data['generate'] = self._last_cmd
    
    def get_providers(self) -> List[Provider]:
        """Get all providers"""
        return list(self._providers.values())
    
    def get_provider(self, name: str) -> Optional[Provider]:
        """Get a provider by name"""
        return self._providers.get(name)
    
    def do_save(self) -> bool:
        """Trigger configuration save"""
        if self._ctx:
            self._ctx.save()
            return True
        return False
    
    def cmd_add_provider(self, args: Namespace) -> bool:
        """Add a new provider"""
        # Validate required fields
        if not args.name:
            logger.error('Provider name is required')
            return False
        if not args.type:
            logger.error('Provider type is required')
            return False
        # Validate url and file are mutually exclusive
        has_url = hasattr(args, 'url') and args.url
        has_file = hasattr(args, 'file') and args.file
        if has_url and has_file:
            logger.error('Provider cannot have both url and file; they are mutually exclusive')
            return False
        if not has_url and not has_file:
            logger.error('Provider must have either url or file')
            return False
        # Check if provider with same name exists
        if args.name in self._providers:
            logger.error(f'Provider with name "{args.name}" already exists')
            return False
        
        # Build and add provider
        try:
            provider = _build_provider_from_args(args)
            self._providers[provider.name] = provider
            logger.info(f'Provider "{provider.name}" added')
            _print_provider(provider)
            return True
        except Exception as e:
            logger.error(f'Failed to build provider: {e}')
            return False
        
    
    def cmd_update_provider(self, args: Namespace) -> bool:
        """Update an existing provider"""

        if not args.name:
            logger.error('Provider name is required')
            return False
        
        # Get existing provider
        existing_provider = self.get_provider(args.name)
        if not existing_provider:
            logger.error(f'Provider "{args.name}" not found')
            return False
        
        # Validate url and file are mutually exclusive if both are provided
        has_url = hasattr(args, 'url') and args.url
        has_file = hasattr(args, 'file') and args.file
        
        if has_url and has_file:
            logger.error('Provider cannot have both url and file; they are mutually exclusive')
            return False

        try:
            # Build updated provider from args
            provider = _modify_provider_from_args(existing_provider, args)
            logger.info(f'Provider "{provider.name}" updated')
            _print_provider(provider)
            return True
        except Exception as e:
            logger.error(f'Failed to update provider: {e}')
            return False
    
    def cmd_remove_provider(self, args: Namespace) -> bool:
        """Remove a provider by name"""
        if not args.name:
            logger.error('Provider name is required')
            return False
        if args.name not in self._providers:
            logger.error(f'Provider "{args.name}" not found')
            return False
        
        del self._providers[args.name]
        logger.info(f'Provider "{args.name}" removed')
        return True
    
    def cmd_list_providers(self) -> None:
        """Print all providers in a readable format"""
        providers = self.get_providers()
        if not providers:
            print('No providers configured')
            return
        print()
        print(f'Total providers: {len(providers)}')
        print('-------------------------')
        for provider in providers:
            _print_provider(provider)

    def set_last_command(self, **kwargs) -> None:
        """Set the last command executed on providers"""
        self._last_cmd = kwargs

    def get_last_command(self) -> Optional[Dict]:
        """Get the last command executed on providers"""
        return self._last_cmd

def _print_provider(provider: Provider):
    print()
    status = 'IGNORED' if provider.ignore else 'ACTIVE'
    print(f'Name: {provider.name}')
    print(f'  Type: {provider.type}')
    print(f'  Status: {status}')
    if provider.local_file:
        print(f'  Local File: {provider.local_file}')
    else:
        print(f'  URL: {provider.url}')
        if provider.update_interval < 0:
            print(f'  Update: once')
        elif provider.update_interval == 0:
            print(f'  Update: immediately')
        else:
            print(f'  Update Interval: {provider.update_interval}s')
    print(f'  Priority: {provider.priority}')
    if provider.last_update > 0:
        from datetime import datetime
        from tzlocal import get_localzone
        dt = datetime.fromtimestamp(provider.last_update, tz=get_localzone())
        print(f'  Last Update: {dt.isoformat()}')
    if provider.process_settings:
        ps = provider.process_settings
        print(f'  Use Rules: {ps.use_rules}')
        if ps.general_group:
            print('  General Groups:')
            for key, value in ps.general_group.items():
                print(f'    {key} => {value}')
        if ps.rewrite_rules:
            print('  Rewrite Rules:')
            for rewrite_rule in ps.rewrite_rules:
                print(f'    {rewrite_rule}')
    print()

def _build_provider_from_args(args: Namespace) -> Provider:
    """Build Provider object from command arguments"""
    kwargs = {
        'name': args.name,
    }
    
    if hasattr(args, 'type') and args.type:
        kwargs['type'] = args.type
    if hasattr(args, 'url') and args.url:
        kwargs['url'] = args.url
    if hasattr(args, 'file') and args.file:
        kwargs['url'] = Provider.get_local_file_url(args.file)
    if hasattr(args, 'priority') and args.priority is not None:
        kwargs['priority'] = args.priority
    if hasattr(args, 'update_interval') and args.update_interval is not None:
        kwargs['update_interval'] = args.update_interval
    if hasattr(args, 'ignore'):
        kwargs['ignore'] = args.ignore
    if hasattr(args, 'use_rules'):
        process_settings = kwargs.get('process_settings', {})
        process_settings['use_rules'] = args.use_rules
        kwargs['process_settings'] = process_settings
    if hasattr(args, 'general_group') and args.general_group:
        process_settings = kwargs.get('process_settings', {})
        general_group_dict = {}
        for mapping in args.general_group:
            key, value = mapping.split('=', 1)
            general_group_dict[key.strip()] = value.strip()
        process_settings['general_group'] = general_group_dict
        kwargs['process_settings'] = process_settings
    
    return Provider(**kwargs)


def _modify_provider_from_args(provider: Provider, args: Namespace) -> Provider:
    """Modify existing Provider object from command arguments"""
    if hasattr(args, 'type') and args.type:
        provider.type = args.type
    if hasattr(args, 'url') and args.url:
        provider.url = args.url
    if hasattr(args, 'file') and args.file:
        provider.local_file = args.file
    if hasattr(args, 'priority') and args.priority is not None:
        provider.priority = args.priority
    if hasattr(args, 'update_interval') and args.update_interval is not None:
        provider.update_interval = args.update_interval
    if hasattr(args, 'ignore'):
        provider.ignore = args.ignore
    if hasattr(args, 'use_rules'):
        if not provider.process_settings:
            provider.process_settings = ProcessSettings()
        provider.process_settings.use_rules = args.use_rules
    if hasattr(args, 'general_group') and args.general_group:
        if not provider.process_settings:
            provider.process_settings = ProcessSettings()
        for mapping in args.general_group:
            key, value = mapping.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key:
                provider.process_settings.general_group_set(key, value)
    if hasattr(args, 'rewrite_rule') and args.rewrite_rule:
        if not provider.process_settings:
            provider.process_settings = ProcessSettings()
        for rewrite_rule in args.rewrite_rule:
            provider.process_settings.rewrite_rule_add(rewrite_rule)
    if hasattr(args, 'remove_rewrite_rule') and args.remove_rewrite_rule:
        if not provider.process_settings:
            provider.process_settings = ProcessSettings()
        for rewrite_rule in args.remove_rewrite_rule:
            provider.process_settings.rewrite_rule_remove(rewrite_rule)
    return provider


class Context(ABC):

    @abstractmethod
    def get_provider_manager(self) -> ProviderManager:
        """Get provider configuration manager"""
        pass

    @abstractmethod
    def get_reader(self, ty: str) -> ISubscribeReader:
        """Get subscribe reader factory"""
        pass

    @abstractmethod
    def get_writer(self, ty: str) -> IConfigWriter:
        """Get subscribe writer"""
        pass

    @abstractmethod
    def get_cache_dir(self) -> str:
        """Get cache directory path"""
        return ''

def _parse_bool(value: str) -> bool:
    """Parse string boolean values"""
    if isinstance(value, bool):
        return value
    if value.lower() in ('true', '1', 'yes', 'on'):
        return True
    if value.lower() in ('false', '0', 'no', 'off'):
        return False
    raise ValueError(f'Invalid boolean value: {value}')

class VariableAction(Action):

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


def cmd_add(args: Namespace, ctx: Context) -> None:
    """Handle 'add' subcommand"""
    mgr = ctx.get_provider_manager()
    if mgr.cmd_add_provider(args):
        mgr.do_save()


def cmd_edit(args: Namespace, ctx: Context) -> None:
    """Handle 'edit' subcommand"""
    mgr = ctx.get_provider_manager()
    if mgr.cmd_update_provider(args):
        mgr.do_save()


def cmd_update(args: Namespace, ctx: Context) -> None:
    """Handle 'update' subcommand"""
    mgr = ctx.get_provider_manager()
    if args.name:
        if mgr.cmd_update_provider(args):
            name = str(args.name)
            provider = mgr.get_provider(name)
            assert provider is not None
            cache_dir = ctx.get_cache_dir()
            reader_factory = lambda ty: ctx.get_reader(ty)
            if cache_dir:
                try:
                    provider.update(reader_factory=reader_factory, cache_root=cache_dir)
                except Exception as e:
                    logger.error('Failed to update provider "%s": %s', name, e)
            mgr.do_save()
    else:
        cache_dir = ctx.get_cache_dir()
        reader_factory = lambda ty: ctx.get_reader(ty)
        if cache_dir:
            for provider in mgr.get_providers():
                if provider.ignore:
                    continue
                if provider.local_file:
                    continue
                try:
                    provider.update(reader_factory=reader_factory, cache_root=cache_dir)
                except Exception as e:
                    logger.error('Failed to update provider "%s": %s', provider.name, e)
        mgr.do_save()


def cmd_remove(args: Namespace, ctx: Context) -> None:
    """Handle 'remove' subcommand"""
    mgr = ctx.get_provider_manager()
    if mgr.cmd_remove_provider(args):
        mgr.do_save()


def cmd_list(args: Namespace, ctx: Context) -> None:
    """Handle 'list' subcommand"""
    mgr = ctx.get_provider_manager()
    mgr.cmd_list_providers()

def cmd_generate(args: Namespace, ctx: Context) -> None:
    """Handle 'generate' subcommand"""
    mgr = ctx.get_provider_manager()
    name: str = args.name
    target: str = args.target
    if not target:
        logger.error('Target configuration type is required')
        return
    template: str = args.template
    if not template:
        logger.error('Template file path is required')
        return
    output: str = args.output
    variables: Dict[str, any] = args.variables if hasattr(args, 'variables') and args.variables else {}

    if name:
        provider = mgr.get_provider(name)
        if not provider:
            logger.error('Provider "%s" not found', name)
            return
        # Generate for specific provider
        print(f'Generating provider: {provider.name} with template: {template} and variables: {variables}')
        # Placeholder for actual generation logic
        try:
            reader_factory = lambda ty: ctx.get_reader(ty)
            info = provider.load(reader_factory=reader_factory, cache_root=ctx.get_cache_dir())
            writer = ctx.get_writer(provider.type)
            proxies, proxy_groups, rules = extract(info)
            template = path.abspath(template)
            with open(template, 'rb') as ifile:
                writer.template(ifile)
            if not output:
                output = writer.get_target_file_name(f'config')
            output = path.abspath(output)
            with open(output, 'wb') as ofile:
                writer.write(ofile, proxies, proxy_groups, rules, **variables)
                logger.info('Wrote generated configuration to %s with %d proxies, %d proxy groups, and %d rules', output, len(proxies), len(proxy_groups), len(rules))
            print(f'Provider "{provider.name}" generated to "{output}"')
            mgr.set_last_command(
                name=name,
                target=target,
                template=template,
                output=output,
                variables=variables
            )
            mgr.do_save()
        except Exception as e:
            logger.error('Failed to generate provider "%s": %s', provider.name, e)
    else:
        reader_factory = lambda ty: ctx.get_reader(ty)
        info_list = []
        for provider in mgr.get_providers():
            # Generate for all providers
            # Placeholder for actual generation logic
            if provider.ignore:
                continue
            try:
                info = provider.load(reader_factory=reader_factory, cache_root=ctx.get_cache_dir())
                if not info:
                    continue
                info.modify_by_name(provider.name)
                info_list.append(info)
                print(f'Generating provider: {provider.name} added to info list')
            except Exception as e:
                logger.error('Failed to generate provider "%s": %s', provider.name, e)
        try:
            proxies, proxy_groups, rules = merge(info_list)
            writer = ctx.get_writer(target)
            template = path.abspath(template)
            with open(template, 'rb') as ifile:
                writer.template(ifile)
            if not output:
                output = writer.get_target_file_name(f'config')
            output = path.abspath(output)
            with open(output, 'wb') as ofile:
                writer.write(ofile, proxies, proxy_groups, rules, **variables)
                logger.info('Wrote generated configuration to %s with %d proxies, %d proxy groups, and %d rules', output, len(proxies), len(proxy_groups), len(rules))
            print(f'All providers generated to "{output}"')
            mgr.set_last_command(
                name='',
                target=target,
                template=template,
                output=output,
                variables=variables
            )
            mgr.do_save()
        except Exception as e:
            logger.error('Failed to generate providers: %s', e)
    

def cmd_regenerate(args: Namespace, ctx: Context) -> None:
    """Handle 'regenerate' subcommand"""
    mgr = ctx.get_provider_manager()
    last_cmd = mgr.get_last_command()
    if not last_cmd:
        logger.error('No previous generate command found')
        return
    args = Namespace(**last_cmd)
    cmd_generate(args, ctx)


def register_subscribe_commands(subparsers: _SubParsersAction):
    """Setup provider manager subcommands"""
    
    # Add subcommand
    add_parser = subparsers.add_parser('add', help='Add a new provider')
    add_parser.add_argument('name', help='Provider name (unique identifier)')
    add_parser.add_argument('--type', required=True, help='Provider type (clash, subscribe, etc.)')
    add_parser.add_argument('--url', help='Remote URL for provider')
    add_parser.add_argument('--file', help='Local file path for provider')
    add_parser.add_argument('--priority', type=int, default=0, help='Provider priority (default: 0)')
    add_parser.add_argument('--update-interval', type=int, default=0, dest='update_interval',
                          help='Update interval in seconds (0=always, -1=never)')
    add_parser.add_argument('--ignore', nargs='?', const='true', type=_parse_bool, default=False,
                          help='Ignore this provider (true/false, default: false)')
    add_parser.add_argument('--use-rules', nargs='?', const='true', type=_parse_bool, default=False,
                          dest='use_rules', help='Use rules from this provider (true/false, default: false)')
    add_parser.add_argument('--general-group', type=str, dest='general_group', action='append',
                          help='General group mapping (key=value, can be repeated)')
    add_parser.set_defaults(func=cmd_add)
    
    # Edit subcommand
    edit_parser = subparsers.add_parser('edit', help='Edit an existing provider')
    edit_parser.add_argument('name', help='Provider name to edit')
    edit_parser.add_argument('--type', help='Provider type (clash, subscribe, etc.)')
    edit_parser.add_argument('--url', help='Remote URL for provider')
    edit_parser.add_argument('--file', help='Local file path for provider')
    edit_parser.add_argument('--priority', type=int, help='Provider priority')
    edit_parser.add_argument('--update-interval', type=int, dest='update_interval',
                           help='Update interval in seconds')
    edit_parser.add_argument('--ignore', nargs='?', const='true', type=_parse_bool,
                          help='Ignore this provider (true/false)')
    edit_parser.add_argument('--use-rules', nargs='?', const='true', type=_parse_bool,
                           dest='use_rules', help='Use rules from this provider (true/false)')
    edit_parser.add_argument('--general-group', type=str, dest='general_group', action='append',
                           help='General group mapping (key=value, can be repeated)')
    edit_parser.add_argument('--rewrite-rule', type=str, dest='rewrite_rule', action='append',
                           help='Rewrite rule (RuleType,Match,Old-Strategy=New-Strategy or RuleType,Match=New-Strategy). Match can be a normal string or regex wrapped by //')
    edit_parser.add_argument('--remove-rewrite-rule', type=str, dest='remove_rewrite_rule', action='append',
                           help='Remove a rewrite rule specification (same format as --rewrite-rule, can be repeated)')
    edit_parser.set_defaults(func=cmd_edit)
    
    # Update subcommand
    update_parser = subparsers.add_parser('update', help='Update provider settings and download latest data')
    update_parser.add_argument('name', nargs='?', default='', help='Provider name to update')
    update_parser.add_argument('--type', help='Provider type (clash, subscribe, etc.)')
    update_parser.add_argument('--url', help='Remote URL for provider')
    update_parser.add_argument('--file', help='Local file path for provider')
    update_parser.add_argument('--priority', type=int, help='Provider priority')
    update_parser.add_argument('--update-interval', type=int, dest='update_interval',
                           help='Update interval in seconds')
    update_parser.add_argument('--ignore', nargs='?', const='true', type=_parse_bool,
                          help='Ignore this provider (true/false)')
    update_parser.add_argument('--use-rules', nargs='?', const='true', type=_parse_bool,
                           dest='use_rules', help='Use rules from this provider (true/false)')
    update_parser.add_argument('--general-group', type=str, dest='general_group', action='append',
                           help='General group mapping (key=value, can be repeated)')
    update_parser.set_defaults(func=cmd_update)
    
    # Remove subcommand
    remove_parser = subparsers.add_parser('remove', help='Remove a provider')
    remove_parser.add_argument('name', help='Provider name to remove')
    remove_parser.set_defaults(func=cmd_remove)
    
    # List subcommand
    list_parser = subparsers.add_parser('list', help='List all providers')
    list_parser.set_defaults(func=cmd_list)


    generate_parser = subparsers.add_parser('generate', help='Generate providers')
    generate_parser.add_argument('--target', '-K', help='Target configuration type', required=True)
    generate_parser.add_argument('--template', '-T', help='Template file path', required=True)
    generate_parser.add_argument('--output', '-o', help='Output file path', default='')
    generate_parser.add_argument('-D', '--variable', dest='variables', action=VariableAction, default={})
    generate_parser.add_argument('name', nargs='?', default='', help='Provider name to generate')
    generate_parser.set_defaults(func=cmd_generate)

    regenerate_parser = subparsers.add_parser('regenerate', help='Regenerate all providers')
    regenerate_parser.set_defaults(func=cmd_regenerate)
