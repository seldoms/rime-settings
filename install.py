#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the settings UI for the current user, never the input method itself."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys


def check_dependencies():
    try:
        import gi
        import yaml
        gi.require_version('Gtk', '4.0')
        gi.require_version('Adw', '1')
        gi.require_version('IBus', '1.0')
        from gi.repository import Adw, Gtk, IBus
        if (Adw.get_major_version(), Adw.get_minor_version()) < (1, 4):
            raise ValueError('libadwaita 需要 >= 1.4')
    except (ImportError, ValueError) as error:
        raise SystemExit(
            f'依赖不满足：{error}\nUbuntu/Debian 请先安装：\n'
            'sudo apt install python3-gi python3-yaml gir1.2-gtk-4.0 '
            'gir1.2-adw-1 gir1.2-ibus-1.0\n然后用 /usr/bin/python3 install.py 重试。'
        )


def exec_quote(value):
    # Desktop Entry Exec quoting, including field-code and backslash escaping.
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    return '"' + escaped.replace('%', '%%').replace('\\', '\\\\') + '"'


def install(data_home, check_only=False):
    check_dependencies()
    if check_only:
        print('依赖检查通过。')
        return
    if os.geteuid() == 0:
        raise SystemExit('请以桌面用户运行，不要 sudo。安装位置仅在用户目录中。')
    source = Path(__file__).resolve().parent
    target = data_home / 'rime-settings'
    applications = data_home / 'applications'
    launcher = applications / 'rime-settings.desktop'
    # Do not install over a Git checkout or copy files onto themselves.
    if target.resolve() == source or (target / '.git').exists():
        raise SystemExit('安装目标是源码目录，请从独立目录安装。')
    files = ['settings.py', 'README.md', 'LICENSE', 'INSTALL_WITH_AGENT.md']
    if any((target / name).exists() for name in files) or launcher.exists():
        backup = data_home / 'rime-settings-install-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        for name in files:
            if (target / name).is_file():
                shutil.copy2(target / name, backup / name)
        if launcher.is_file():
            shutil.copy2(launcher, backup / launcher.name)
        print(f'旧版界面已备份：{backup}')
    target.mkdir(parents=True, exist_ok=True)
    applications.mkdir(parents=True, exist_ok=True)
    for name in files:
        shutil.copy2(source / name, target / name)
    launcher.write_text(
        '[Desktop Entry]\nType=Application\nName=雾凇拼音设置\n'
        'Name[en]=Rime Settings\nComment=调整候选词数量、排列与中英文切换\n'
        f'Exec=/usr/bin/python3 {exec_quote(target / "settings.py")}\n'
        'Icon=input-keyboard-symbolic\nTerminal=false\nCategories=Settings;\n'
        'Keywords=Rime;拼音;输入法;雾凇;候选词;\nStartupNotify=true\n', encoding='utf-8')
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(applications)], check=False)
    print('安装完成！在应用菜单搜索「雾凇拼音设置」。')
    print(f'也可直接运行：/usr/bin/python3 {target / "settings.py"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只检查依赖，不安装')
    parser.add_argument('--data-home', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')),
                        help='用户数据目录，默认遵循 XDG_DATA_HOME')
    args = parser.parse_args()
    data_home = args.data_home.expanduser().absolute()
    if '\n' in str(data_home) or '\r' in str(data_home):
        parser.error('安装路径不能包含换行')
    install(data_home, args.check)
