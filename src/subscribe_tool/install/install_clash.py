import os
import sys
import gzip
import shutil
import stat
import platform
import re
from typing import Dict, Tuple, override
from pathlib import Path
from urllib import request
from zipfile import ZipFile
from . import Installer
from ..utils import read_input, read_confirm, download_file, template, USER_AGENT


# Default URLs for Clash binary and MMDB
DEFAULT_CLASH_RELEASE_LATEST_VERSION_URL = "https://github.com/MetaCubeX/mihomo/releases/latest"
DEFAULT_CLASH_RELEASE_URL = "https://github.com/MetaCubeX/mihomo/releases/download/{version}/mihomo-{os}-{arch}-{version}.{compress}"
DEFAULT_RESOURCE_URL = "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/{resource}"
DEFAULT_RESOURCE_ITEMS = [
    "Country.mmdb",
    "geoip.dat",
    "geoip.metadb",
    "geosite.dat",
]
DEFAULT_UI_URL = ""
LATEST_VERSION = "v1.18.4"  # You may want to fetch this dynamically from GitHub API


class ClashInstaller(Installer):
    
    @staticmethod
    def _detect_clash_latest_version() -> str:
        """
        Detect the latest Clash version by following redirects from the releases/latest URL.
        Returns version string like 'v1.18.4'
        """
        try:
            req = request.Request(DEFAULT_CLASH_RELEASE_LATEST_VERSION_URL)
            req.add_header('User-Agent', USER_AGENT)
            
            # urlopen follows redirects by default
            response = request.urlopen(req, timeout=5)
            final_url = response.geturl()
            
            # Extract version from URL like: https://github.com/MetaCubeX/mihomo/releases/tag/v1.18.4
            match = re.search(r'/tag/(v[\d.]+)', final_url)
            if match:
                version = match.group(1)
                print(f"[*] Detected latest Clash version: {version}")
                return version
            else:
                raise ValueError(f"Could not extract version from redirect URL: {final_url}")
        except Exception as e:
            print(f"[!] Failed to detect latest version: {e}")
            print(f"[*] Falling back to default version: {LATEST_VERSION}")
            return LATEST_VERSION
    
    @staticmethod
    def _detect_platform() -> Tuple[str, str, str]:
        """Detect OS and architecture for Clash binary download."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        # Map system names
        if system == 'linux':
            os_name = 'linux'
            compress = 'gz'
        elif system == 'darwin':
            os_name = 'darwin'
            compress = 'gz'
        elif system == 'windows':
            os_name = 'windows'
            compress = 'zip'
        else:
            raise ValueError(f"Unsupported OS: {system}")
        
        # Map architecture names
        if machine in ('x86_64', 'amd64'):
            arch = 'amd64-v3'
        elif machine in ('aarch64', 'arm64'):
            arch = 'arm64'
        else:
            raise ValueError(f"Unsupported architecture: {machine}")
        
        return os_name, arch, compress
    
    @staticmethod
    def _get_repo_root() -> Path:
        """Get the repository root directory."""
        return Path(os.path.curdir)
    
    def install(self, cfg: Dict, location: str, **kwargs):
        """Install Clash with all required components."""
        try:
            # Ensure location directory exists
            location_path = Path(location)
            location_path.mkdir(parents=True, exist_ok=True)
            
            # Get platform info
            os_name, arch, compress = self._detect_platform()
            
            # Detect latest version
            latest_version = cfg.get('clash_version')
            if latest_version:
                k = read_confirm(f"Detected Clash version in config: {latest_version}. Do you want to use it? (y/n): ", True)
                if not k:
                    latest_version = None
            
            if not latest_version:
                print(f"[*] Detecting latest Clash version...")
                latest_version = self._detect_clash_latest_version()
                cfg['clash_version'] = latest_version
            
            # Prompt for download URL
            default_url = DEFAULT_CLASH_RELEASE_URL.format(
                version=latest_version,
                os=os_name,
                arch=arch,
                compress=compress
            )

            clash_url = read_input(
                "Enter Clash download URL (default: {}): ",
                default_url
            )

            previously_url = cfg.get('clash_download_url')
            previously_download = cfg.get('clash_download')
            skip_download = False
            if previously_url == clash_url and previously_download and os.path.isfile(previously_download):
                skip_download = read_confirm(f"Clash already downloaded at {previously_download}. Do you want to reuse it? (y/n): ", True)
            
            if not skip_download:
                print(f"[*] Downloading Clash binary from {clash_url}...")
                clash_file = download_file(clash_url, str(location_path), f'clash.{compress}')
                cfg['clash_download_url'] = clash_url
                cfg['clash_download'] = str(clash_file)
            else:
                clash_file = previously_download
                print(f"[*] Reusing previously downloaded Clash binary at {clash_file}")
            
            # Extract binary
            clash_binary_filename: str = None
            print(f"[*] Extracting binary...")
            if clash_file.endswith('.gz'):
                # Decompress gzip
                with gzip.open(clash_file, 'rb') as gz_in:
                    clash_binary_filename = os.path.basename(clash_file)
                    clash_binary_filename = clash_binary_filename[:-3]  # Remove .gz
                    if clash_binary_filename.endswith(latest_version):
                        i = len(latest_version)
                        clash_binary_filename = clash_binary_filename[:-i]  # Remove version
                        if clash_binary_filename.endswith('-'):
                            clash_binary_filename = clash_binary_filename[:-1]  # Remove trailing '-'
                    extracted_path = location_path / clash_binary_filename
                    with open(extracted_path, 'wb') as f:
                        shutil.copyfileobj(gz_in, f)
            elif clash_file.endswith('.zip'):
                # Extract zip
                with ZipFile(clash_file, 'r') as zip_ref:
                    filenames = zip_ref.namelist()
                    for filename in filenames:
                        if filename.startswith('mihomo') and filename.endswith('.exe'):
                            clash_binary_filename = filename
                            break
                    zip_ref.extractall(location_path, filenames)
            else:
                print(f"[!] Unknown compression format for {clash_file}")
                return
            if not clash_binary_filename:
                print(f"[!] Could not find extracted Clash binary in the archive")
                return
            clash_binary = os.path.join(location_path, clash_binary_filename)
            cfg['clash_binary'] = clash_binary
            
            # Make executable on Unix-like systems
            if os_name != 'windows':
                clash_binary_path = Path(clash_binary)
                clash_binary_path.chmod(clash_binary_path.stat().st_mode | stat.S_IEXEC)
                print(f"[+] Made {clash_binary} executable")

            # Prompt for Resource URL
            rsc_url = read_input(
                "Enter resource download URL (default: {}): ",
                DEFAULT_RESOURCE_URL
            )

            # Download resources
            skip_download_resources = False
            previously_resource_url = cfg.get('resource_download_url')
            previously_resource_download = cfg.get('resource_download')
            if previously_resource_url == rsc_url and isinstance(previously_resource_download, list) and len(previously_resource_download) >= len(DEFAULT_RESOURCE_ITEMS):
                reuse_resources = read_confirm(f"Resource download URL unchanged. Do you want to skip re-downloading resources? (y/n): ", True)
                if reuse_resources:
                    skip_download_resources = True

            if not skip_download_resources:
                previously_resource_download = []
                print(f"[*] Downloading resources...")
                for resource_item in DEFAULT_RESOURCE_ITEMS:
                    url = rsc_url.format(resource=resource_item)
                    print(f"[*] Downloading {resource_item} from {url}...")
                    dowloaded = download_file(url, str(location_path), resource_item)
                    print(f"[+] Downloaded {resource_item} to {dowloaded}")
                    previously_resource_download.append(str(dowloaded))
                cfg['resource_download_url'] = rsc_url
                cfg['resource_download'] = previously_resource_download
                            
            # Generate service file (only for Linux)
            if os_name == 'linux':

                # Prompt for service user
                service_user = read_input(
                    "Enter service user to run Clash (default: {}): ",
                    "vpnuser"
                )
                
                # Get Python executable path
                python_exe = sys.executable
                
                if not 'assets_root' in kwargs:
                    print(f"[!] assets_root not provided, skipping service file generation")
                    return
                assets_root = kwargs['assets_root']

                if not 'cfg_file' in kwargs:
                    print(f"[!] cfg_file not provided, skipping service file generation")
                    return
                cfg_file = kwargs['cfg_file']

                print(f"[*] Generating systemd service file...")
                assets_dir = Path(assets_root)
                service_template = assets_dir / 'clash.service'
                service_file = location_path / 'clash.service'
                
                with open(service_template, 'r') as infile:
                    with open(service_file, 'w') as outfile:
                        template(
                            infile, outfile,
                            vpnuser=service_user,
                            clash_dir=str(location_path),
                            clash_exe=clash_binary,
                            python_exe=python_exe,
                            config_file=cfg_file
                        )
                        cfg['service_file'] = str(service_file)

                restart_service_template = assets_dir / 'clash-restart.service'
                restart_service_file = location_path / 'clash-restart.service'
                with open(restart_service_template, 'r') as infile:
                    with open(restart_service_file, 'w') as outfile:
                        shutil.copyfileobj(infile, outfile)
                        cfg['service_restart_file'] = str(restart_service_file)

                restart_timer_template = assets_dir / 'clash-restart.timer'
                restart_timer_file = location_path / 'clash-restart.timer'
                with open(restart_timer_template, 'r') as infile:
                    with open(restart_timer_file, 'w') as outfile:
                        shutil.copyfileobj(infile, outfile)
                        cfg['service_restart_timer_file'] = str(restart_timer_file)

                print(f"[+] Service file generated at {service_file}")
                print(f"[+] Restart service file generated at {restart_service_file}")
                print(f"[+] Restart timer file generated at {restart_timer_file}")
                print(f"[!] To install systemd service, run:")
                print(f"    sudo cp {service_file} /usr/local/lib/systemd/system/clash.service")
                print(f"    sudo cp {restart_service_file} /usr/local/lib/systemd/system/clash-restart.service")
                print(f"    sudo cp {restart_timer_file} /usr/local/lib/systemd/system/clash-restart.timer")
                print(f"    sudo systemctl daemon-reload")
                print(f"    sudo systemctl enable clash.service")
                print(f"    sudo systemctl enable clash-restart.timer")
            
            print(f"\n[+] Clash installation completed successfully!")
            
        except Exception as e:
            print(f"[-] Installation failed: {e}")
            raise

    @override
    def uninstall(self, cfg: Dict):
        """Uninstall Clash and remove all components."""
        try:
            location = cfg.get('location')
            if not location:
                print("[-] No installation location found in config")
                return
            
            location_path = Path(location)
            
            # Ask for confirmation
            if not read_confirm(f"Are you sure you want to uninstall Clash from {location}? (y/n): "):
                print("[*] Uninstall cancelled")
                return
            
            # Remove service file if exists
            service_file = cfg.get('service_file')
            if service_file and Path(service_file).exists():
                print(f"[!] To remove systemd service, run:")
                print(f"    sudo systemctl stop clash-restart.timer")
                print(f"    sudo systemctl stop clash.service")
                print(f"    sudo systemctl disable clash-restart.timer")
                print(f"    sudo systemctl disable clash.service")
                print(f"    sudo rm /usr/local/lib/systemd/system/clash.service")
                print(f"    sudo rm /usr/local/lib/systemd/system/clash-restart.service")
                print(f"    sudo rm /usr/local/lib/systemd/system/clash-restart.timer")
                print(f"    sudo systemctl daemon-reload")
            
            # # Remove installation directory
            # if location_path.exists():
            #     shutil.rmtree(location_path)
            #     print(f"[+] Removed installation directory: {location}")
            
            print(f"[+] Clash uninstalled successfully")
            
        except Exception as e:
            print(f"[-] Uninstallation failed: {e}")
            raise