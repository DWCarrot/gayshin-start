import sys
from os import path
from json import dump, load
from util import template

def read_input(prompt: str, default: str) -> str:
    value = input(prompt.format(default))
    if not value:
        return default
    return value

def install(root: str, install_log: str):
    print('># install clash service start')
    vpnuser = read_input('execute user name [{}]: ', 'vpnuser')
    clash_dir = read_input('clash directory [{}]: ', f'/home/{vpnuser}/clash')    
    clash_exe = read_input('clash executable [{}]: ', 'clash.meta')
    repo_dir = path.split(root)[0]
    ctrl_host = read_input('control host [{}] (if run for local it should be something like \'127.0.0.1:9090\'): ', '0.0.0.0:9090')
    ctrl_passwd = read_input('control password [{}]: ', '')
    variables = dict(
        clash_dir=path.abspath(clash_dir),
        clash_exe=clash_exe,
        vpnuser=vpnuser,
        repo_dir=repo_dir,
        ctrl_host=ctrl_host,
        ctrl_passwd=ctrl_passwd
    )
    print('variables:', variables)

    print('')

    print('># writing service file')
    ifile_name = path.join(root, 'clash.service')
    ofile_name = path.join(clash_dir, 'clash.service')
    with open(ifile_name, 'r') as ifile:
        with open(ofile_name, 'w') as ofile:
            template(ifile, ofile, **variables)
    print('># service file write to', ofile_name)
    ofile_name_clash_service = ofile_name

    print('># writing service timer file')
    ifile_name = path.join(root, 'clash.timer')
    ofile_name = path.join(clash_dir, 'clash.timer')
    with open(ifile_name, 'r') as ifile:
        with open(ofile_name, 'w') as ofile:
            template(ifile, ofile, **variables)
    print('># service timer file write to', ofile_name)
    ofile_name_clash_timer = ofile_name

    print('># writing service shell')
    ifile_name = path.join(root, 'clash.subscribe.sh')
    ofile_name = path.join(clash_dir, 'clash.subscribe.sh')
    with open(ifile_name, 'r') as ifile:
        with open(ofile_name, 'w') as ofile:
            template(ifile, ofile, **variables)
    print('># service shell write to', ofile_name)
    ofile_name_clash_shell = ofile_name
    
    from json import dump
    with open(install_log, 'w') as log:
        dump(variables, log)

    print('># install operations')
    print('')
    print(f'chmod +x {ofile_name_clash_shell}')
    print(f'sudo cp {ofile_name_clash_service} /usr/local/lib/systemd/system/')
    print(f'sudo cp {ofile_name_clash_timer} /usr/local/lib/systemd/system/')
    print(f'sudo systemctl enable clash.service')

    print('')
    print('># install clash service end')

def uninstall(install_log: str):
    from json import load
    with open(install_log, 'r') as log:
        variables = load(log)
    print('># uninstall operations')
    print('')
    print(f'sudo systemctl disable clash.service')
    print(f'sudo rm /usr/local/lib/systemd/system/clash.service')
    print(f'sudo rm /usr/local/lib/systemd/system/clash.timer')
    print(f'rm -r {variables["clash_dir"]}')


if __name__ == '__main__':
    root = path.split(__file__)[0]
    install_log = path.join(root, '~install.log')
    args = sys.argv[1:]
    if len(args) == 0 or args[0] in ('install', 'i'):
        install(root, install_log)
    elif len(args) > 0 and args[0] in ('uninstall', 'u'):
        uninstall(install_log)