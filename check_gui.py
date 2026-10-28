# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise Save, then restore the original config files and effective values."""
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Gio
import settings

original = settings.load_settings()
paths = [settings.RIME_DIR / name for name in ('default.custom.yaml', 'ibus_rime.custom.yaml')]
original_files = {path: path.read_text(encoding='utf-8') if path.exists() else None for path in paths}
state = {'phase': 0, 'start': time.monotonic(), 'failed': False}


def check():
    app = Gio.Application.get_default()
    if app is None or app.window is None:
        return True
    try:
        if time.monotonic() - state['start'] > 100:
            raise TimeoutError('GUI apply timed out')
        if state['phase'] == 0:
            app.count.set_value(9)
            app.layout.set_selected(1)
            app.apply.emit('clicked')
            state['phase'] = 1
        elif state['phase'] == 1 and not app.busy:
            assert '已应用' in app.status.get_label(), app.status.get_label()
            assert settings.lookup(settings.read_yaml(settings.RIME_DIR / 'build/default.yaml'), 'menu/page_size') == 9
            assert settings.lookup(settings.read_yaml(settings.RIME_DIR / 'build/ibus_rime.yaml'), 'style/horizontal') is False
            print('PASS: Save button deployed 9 candidates / vertical layout', flush=True)
            app.count.set_value(original['page_size'])
            app.layout.set_selected(0 if original['horizontal'] else 1)
            app.shift.set_selected(app.actions.index(original['shift_action']))
            app.apply.emit('clicked')
            state['phase'] = 2
        elif state['phase'] == 2 and not app.busy:
            assert '已应用' in app.status.get_label(), app.status.get_label()
            assert settings.load_settings() == original
            assert settings.lookup(settings.read_yaml(settings.RIME_DIR / 'build/default.yaml'), 'menu/page_size') == original['page_size']
            print('PASS: original preferences restored and compiled', flush=True)
            app.quit()
            return False
    except Exception as error:
        state['failed'] = True
        print('ERROR:', error, flush=True)
        app.quit()
        return False
    return True


GLib.timeout_add(250, check)
try:
    settings.run_gui(application_id='local.rime.Settings.Test')
finally:
    for path, text in original_files.items():
        if text is None:
            path.unlink(missing_ok=True)
        else:
            settings.atomic_write(path, text)
    settings.redeploy(original)
    print('Original configuration files restored, including comments.', flush=True)
if state['failed']:
    raise SystemExit(1)
