#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Local settings for IBus-Rime. No network access or elevated privileges."""
from pathlib import Path
from datetime import datetime
import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

import yaml

RIME_DIR = Path.home() / '.config/ibus/rime'


def read_yaml(path):
    if not path.exists():
        return {}
    result = yaml.safe_load(path.read_text(encoding='utf-8'))
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise ValueError(f'{path.name} 的内容必须是配置映射')
    return result


def lookup(data, key, default=None):
    if key in data:
        return data[key]
    parts = key.split('/')
    for index in range(len(parts) - 1, 0, -1):
        parent = '/'.join(parts[:index])
        if parent in data and isinstance(data[parent], dict):
            return lookup(data[parent], '/'.join(parts[index:]), default)
    return default


def set_patch(document, key, value):
    patch = document.setdefault('patch', {})
    if not isinstance(patch, dict):
        raise ValueError('patch 必须是配置映射，请先检查现有配置')
    parts = key.split('/')
    for index in range(len(parts) - 1, 0, -1):
        parent = '/'.join(parts[:index])
        if parent in patch and isinstance(patch[parent], dict):
            nested = {'patch': patch[parent]}
            set_patch(nested, '/'.join(parts[index:]), value)
            patch.pop(key, None)
            return
    patch[key] = value


def load_settings(root=RIME_DIR):
    def value(custom, compiled, key, fallback):
        return lookup(read_yaml(root / custom).get('patch', {}), key,
                      lookup(read_yaml(root / 'build' / compiled), key, fallback))
    return {
        'page_size': int(value('default.custom.yaml', 'default.yaml', 'menu/page_size', 5)),
        'horizontal': bool(value('ibus_rime.custom.yaml', 'ibus_rime.yaml', 'style/horizontal', True)),
        'shift_action': str(value('default.custom.yaml', 'default.yaml',
                                  'ascii_composer/switch_key/Shift_L', 'commit_code')),
    }


def validate(values):
    if type(values.get('page_size')) is not int or not 1 <= values['page_size'] <= 9:
        raise ValueError('候选词数量需要在 1 到 9 之间')
    if type(values.get('horizontal')) is not bool:
        raise ValueError('候选词排列设置无效')
    if values.get('shift_action') not in {'commit_code', 'commit_text', 'clear', 'inline_ascii', 'noop', 'set_ascii_mode', 'unset_ascii_mode'}:
        raise ValueError('Shift 切换设置无效')


def atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_settings(values, root=RIME_DIR):
    validate(values)
    if not (root / 'rime_ice.schema.yaml').is_file():
        raise ValueError('尚未找到雾凇拼音，请先按 README 安装 IBus-Rime 和雾凇拼音。')
    # Parse both files before writing either; malformed files stay untouched.
    documents = {name: copy.deepcopy(read_yaml(root / name)) for name in
                 ('default.custom.yaml', 'ibus_rime.custom.yaml')}
    set_patch(documents['default.custom.yaml'], 'menu/page_size', values['page_size'])
    set_patch(documents['default.custom.yaml'], 'ascii_composer/switch_key/Shift_L', values['shift_action'])
    set_patch(documents['ibus_rime.custom.yaml'], 'style/horizontal', values['horizontal'])
    backup = root / 'settings-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    originals = {}
    for name in documents:
        path = root / name
        originals[name] = path.read_text(encoding='utf-8') if path.exists() else None
        if originals[name] is not None:
            (backup / name).write_text(originals[name], encoding='utf-8')
    (backup / 'manifest.json').write_text(json.dumps({'previously_absent': [n for n, v in originals.items() if v is None]}, indent=2))
    written = []
    try:
        for name, doc in documents.items():
            atomic_write(root / name, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
            written.append(name)
    except Exception:
        for name in written:
            if originals[name] is None:
                (root / name).unlink()
            else:
                atomic_write(root / name, originals[name])
        raise
    return backup


def redeploy(values, root=RIME_DIR):
    import gi
    gi.require_version('IBus', '1.0')
    from gi.repository import IBus, GLib, Gio
    IBus.init()
    bus = IBus.Bus.new()
    if not bus.is_connected():
        raise RuntimeError('配置已保存，但未连接桌面输入法。请从右上角 Rime 菜单选择「部署」。')
    bus.preload_engines(['rime'])
    connection = bus.get_connection()

    def call(path, interface, method, parameters=None):
        return connection.call_sync('im.rime.Rime', path, interface, method, parameters,
                                    None, Gio.DBusCallFlags.NONE, 10000, None)

    engine_path = None

    def drain():
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

    try:
        # A dedicated engine avoids stealing focus from the settings window.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                result = call('/org/freedesktop/IBus/Factory', 'org.freedesktop.IBus.Factory',
                              'CreateEngine', GLib.Variant('(s)', ('rime',)))
                engine_path = result.unpack()[0]
                break
            except GLib.Error:
                time.sleep(0.2)
        else:
            raise RuntimeError('配置已保存，Rime 暂未就绪。请从右上角 Rime 菜单选择「部署」。')
        previous = (root / 'user.yaml').stat().st_mtime_ns if (root / 'user.yaml').exists() else 0
        call(engine_path, 'org.freedesktop.IBus.Engine', 'PropertyActivate',
             GLib.Variant('(su)', ('deploy', 0)))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            drain()
            time.sleep(0.15)
            try:
                default = read_yaml(root / 'build/default.yaml')
                frontend = read_yaml(root / 'build/ibus_rime.yaml')
                if ((root / 'user.yaml').stat().st_mtime_ns > previous
                    and lookup(default, 'menu/page_size') == values['page_size']
                    and lookup(default, 'ascii_composer/switch_key/Shift_L') == values['shift_action']
                    and lookup(frontend, 'style/horizontal') == values['horizontal']):
                    return
            except (OSError, yaml.YAMLError):
                continue
        raise RuntimeError('配置已保存，但尚未确认部署完成。请从右上角 Rime 菜单选择「部署」。')
    finally:
        if engine_path:
            call(engine_path, 'org.freedesktop.IBus.Service', 'Destroy')


def run_gui(application_id='local.rime.Settings'):
    # A stale desktop environment may still point at the previous Fcitx setup.
    # Limit this choice to our GTK process so the test entry uses IBus-Rime.
    os.environ['GTK_IM_MODULE'] = 'ibus'
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Adw, Gtk, GLib, Gio
    if (Adw.get_major_version(), Adw.get_minor_version()) < (1, 4):
        raise RuntimeError('需要 libadwaita 1.4 或更新版本（推荐 Ubuntu 24.04 及以上）。')

    class SettingsApp(Adw.Application):
        def __init__(self):
            super().__init__(application_id=application_id)
            self.window = None

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Adw.ApplicationWindow(application=self, title='雾凇拼音设置', default_width=600, default_height=760)
            self.window.connect('close-request', lambda *_: getattr(self, 'busy', False))
            toolbar = Adw.ToolbarView()
            toolbar.add_top_bar(Adw.HeaderBar())
            self.window.set_content(toolbar)
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            toolbar.set_content(scroll)
            clamp = Adw.Clamp(maximum_size=560, margin_start=24, margin_end=24, margin_top=12, margin_bottom=24)
            scroll.set_child(clamp)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
            clamp.set_child(box)
            title = Gtk.Label(label='让拼音顺手一点', xalign=0)
            title.add_css_class('title-1')
            box.append(title)
            subtitle = Gtk.Label(label='雾凇拼音 · 简体全拼', xalign=0)
            subtitle.add_css_class('dim-label')
            box.append(subtitle)

            group = Adw.PreferencesGroup(title='候选词')
            self.count = Adw.SpinRow.new_with_range(1, 9, 1)
            self.count.set_title('每页候选词数量')
            self.count.set_subtitle('支持 1–9 个，数字键选词')
            group.add(self.count)
            self.layout = Adw.ComboRow(title='排列方向', model=Gtk.StringList.new(['横向排列', '竖向排列']))
            group.add(self.layout)
            box.append(group)
            keyboard = Adw.PreferencesGroup(title='中英文切换')
            self.actions = ['commit_code', 'commit_text', 'clear', 'noop', 'inline_ascii', 'set_ascii_mode', 'unset_ascii_mode']
            self.shift = Adw.ComboRow(title='左 Shift 按键', subtitle='打字过程中按下时的行为', model=Gtk.StringList.new([
                '切换中英文，保留拼音字母', '切换中英文，提交候选词', '切换中英文，清空待选内容', '不切换中英文',
                '临时英文，回车后回到中文', '切换到英文', '切换到中文']))
            keyboard.add(self.shift)
            box.append(keyboard)

            self.form = [group, keyboard]
            footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            self.apply = Gtk.Button(label='保存并应用')
            self.apply.add_css_class('suggested-action')
            self.apply.add_css_class('pill')
            self.apply.set_halign(Gtk.Align.FILL)
            self.apply.connect('clicked', self.on_apply)
            footer.append(self.apply)
            self.status = Gtk.Label(label='保存前自动备份，应用后即可试打。', wrap=True, xalign=0)
            self.status.add_css_class('dim-label')
            self.status.set_selectable(True)
            footer.append(self.status)
            box.append(footer)

            test = Adw.PreferencesGroup(title='试打一段', description='切换到 Rime 后，输入 nihao 或任意拼音试试。')
            test.add(Adw.EntryRow(title='在这里输入'))
            box.append(test)
            advanced = Gtk.Button(label='打开配置文件夹', halign=Gtk.Align.CENTER)
            advanced.add_css_class('flat')
            advanced.connect('clicked', lambda *_: Gio.AppInfo.launch_default_for_uri(RIME_DIR.as_uri(), None))
            box.append(advanced)
            self.reload()
            self.window.present()

        def reload(self):
            try:
                if not (RIME_DIR / 'rime_ice.schema.yaml').is_file():
                    raise ValueError('未找到雾凇拼音，请先按项目 README 安装输入法和词库。')
                values = load_settings()
                self.count.set_value(values['page_size'])
                self.layout.set_selected(0 if values['horizontal'] else 1)
                self.shift.set_selected(self.actions.index(values['shift_action']))
            except Exception as error:
                self.status.set_label(f'读取配置失败：{error}')
                self.apply.set_sensitive(False)

        def on_apply(self, *_):
            values = {'page_size': int(self.count.get_value()), 'horizontal': self.layout.get_selected() == 0,
                      'shift_action': self.actions[self.shift.get_selected()]}
            self.busy = True
            self.apply.set_sensitive(False)
            for widget in self.form:
                widget.set_sensitive(False)
            self.apply.set_label('正在应用…')
            self.status.set_label('正在备份配置并重新部署，请稍候。')
            def worker():
                try:
                    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--apply', json.dumps(values)],
                                            capture_output=True, text=True, timeout=110)
                    if result.returncode:
                        message = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else '应用失败，请重试。'
                    else:
                        message = f'已应用 · 每页 {values["page_size"]} 个候选词。可以在下方试打。'
                except Exception as error:
                    message = f'应用未完成：{error}'
                GLib.idle_add(self.finish, message)
            threading.Thread(target=worker, daemon=True).start()

        def finish(self, message):
            self.busy = False
            self.apply.set_sensitive(True)
            for widget in self.form:
                widget.set_sensitive(True)
            self.apply.set_label('保存并应用')
            self.status.set_label(message)
            return False

    return SettingsApp().run(None)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--apply':
        try:
            import fcntl
            if not RIME_DIR.is_dir():
                raise ValueError('尚未安装雾凇拼音，请先按 README 完成安装。')
            lock = (RIME_DIR / '.rime-settings.lock').open('a')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('另一个设置窗口正在部署，请稍候再试。')
            settings = json.loads(sys.argv[2])
            backup = save_settings(settings)
            redeploy(settings)
            print(json.dumps({'ok': True, 'backup': str(backup)}, ensure_ascii=False))
        except Exception as error:
            print(str(error), file=sys.stderr)
            sys.exit(1)
    else:
        sys.exit(run_gui())
