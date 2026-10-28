# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture only this application's widget; never the desktop or personal data."""
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gsk', '4.0')
from gi.repository import Adw, Gtk, GLib, Gio, Gsk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import settings

output = Path(__file__).resolve().parent / 'images'
output.mkdir(exist_ok=True)
errors = []


def capture(name):
    app = Gio.Application.get_default()
    renderer = None
    try:
        window = app.get_active_window()
        snapshot = Gtk.Snapshot.new()
        Gtk.WidgetPaintable.new(window).snapshot(snapshot, window.get_width(), window.get_height())
        renderer = Gsk.Renderer.new_for_surface(window.get_surface())
        texture = renderer.render_texture(snapshot.to_node(), None)
        if not texture.save_to_png(str(output / name)):
            raise RuntimeError('Failed to save screenshot')
        print(output / name, flush=True)
    except Exception as error:
        errors.append(error)
    finally:
        if renderer:
            renderer.unrealize()


def light():
    app = Gio.Application.get_default()
    app.window.set_focus(None)
    # Demonstrate the controls without saving or changing the user's settings.
    app.count.set_value(9)
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    GLib.timeout_add_seconds(2, after_light)
    return False


def after_light():
    capture('settings-light.png')
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    GLib.timeout_add_seconds(2, after_dark)
    return False


def after_dark():
    capture('settings-dark.png')
    Gio.Application.get_default().quit()
    return False


GLib.timeout_add_seconds(2, light)
settings.run_gui(application_id='local.rime.Settings.Screenshots')
if errors:
    raise SystemExit(str(errors))
