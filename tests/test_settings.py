# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration regression checks. Never use a real Rime directory."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import settings
import install


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'rime_ice.schema.yaml').write_text('schema: {schema_id: rime_ice}\n')
        self.values = {'page_size': 9, 'horizontal': False, 'shift_action': 'noop'}

    def test_preserves_other_options_and_original_text(self):
        source = '# My comment\npatch:\n  schema_list: [{schema: rime_ice}]\n  menu:\n    page_size: 5\n    other: keep\n  unknown/option: true\n'
        (self.root / 'default.custom.yaml').write_text(source)
        backup = settings.save_settings(self.values, self.root)
        saved = settings.read_yaml(self.root / 'default.custom.yaml')['patch']
        self.assertEqual(saved['schema_list'], [{'schema': 'rime_ice'}])
        self.assertEqual(saved['menu'], {'page_size': 9, 'other': 'keep'})
        self.assertTrue(saved['unknown/option'])
        self.assertEqual((backup / 'default.custom.yaml').read_text(), source)
        self.assertEqual(json.loads((backup / 'manifest.json').read_text())['previously_absent'], ['ibus_rime.custom.yaml'])
        self.assertEqual(settings.load_settings(self.root), self.values)

    def test_partial_flattening_preserves_siblings(self):
        (self.root / 'default.custom.yaml').write_text('patch:\n  ascii_composer/switch_key:\n    Shift_L: commit_text\n    Shift_R: clear\n')
        settings.save_settings(self.values, self.root)
        patch_data = settings.read_yaml(self.root / 'default.custom.yaml')['patch']
        self.assertEqual(settings.lookup(patch_data, 'ascii_composer/switch_key/Shift_R'), 'clear')
        self.assertEqual(settings.lookup(patch_data, 'ascii_composer/switch_key/Shift_L'), 'noop')

    def test_invalid_input_does_not_write(self):
        for value in (0, 10, True, '9'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings.save_settings(dict(self.values, page_size=value), self.root)
        self.assertFalse((self.root / 'settings-backups').exists())
        self.assertFalse((self.root / 'default.custom.yaml').exists())

    def test_malformed_second_file_leaves_first_untouched(self):
        original = 'patch: {unrelated: keep}\n'
        (self.root / 'default.custom.yaml').write_text(original)
        (self.root / 'ibus_rime.custom.yaml').write_text('patch: [wrong]\n')
        with self.assertRaises(ValueError):
            settings.save_settings(self.values, self.root)
        self.assertEqual((self.root / 'default.custom.yaml').read_text(), original)
        self.assertFalse((self.root / 'settings-backups').exists())

    def test_failed_second_write_rolls_back_first(self):
        original = '# Original\npatch: {menu/page_size: 5}\n'
        (self.root / 'default.custom.yaml').write_text(original)
        writer = settings.atomic_write
        def fail_frontend(path, content):
            if path.name == 'ibus_rime.custom.yaml':
                raise OSError('Simulated write failure')
            writer(path, content)
        with patch.object(settings, 'atomic_write', side_effect=fail_frontend):
            with self.assertRaises(OSError):
                settings.save_settings(self.values, self.root)
        self.assertEqual((self.root / 'default.custom.yaml').read_text(), original)

    def test_requires_existing_rime_ice(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ValueError):
                settings.save_settings(self.values, Path(empty))
            self.assertEqual(list(Path(empty).iterdir()), [])

    def test_fallback_to_compiled_configuration(self):
        (self.root / 'build').mkdir()
        (self.root / 'build/default.yaml').write_text('menu: {page_size: 7}\nascii_composer: {switch_key: {Shift_L: clear}}\n')
        (self.root / 'build/ibus_rime.yaml').write_text('style: {horizontal: false}\n')
        self.assertEqual(settings.load_settings(self.root), {'page_size': 7, 'horizontal': False, 'shift_action': 'clear'})


class InstallerTests(unittest.TestCase):
    def test_install_with_space_and_updates_preserve_original(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'data with spaces'
            with patch.object(install, 'check_dependencies'), patch.object(install.os, 'geteuid', return_value=1000), patch.object(install.subprocess, 'run'):
                install.install(target)
                launcher = target / 'applications/rime-settings.desktop'
                self.assertIn(f'Exec=/usr/bin/python3 "{target}/rime-settings/settings.py"', launcher.read_text())
                self.assertIn('Name=雾凇拼音设置', launcher.read_text())
                self.assertTrue((target / 'rime-settings/INSTALL_WITH_AGENT.md').is_file())
                (target / 'rime-settings/settings.py').write_text('# previous installation\n')
                install.install(target)
                backups = list((target / 'rime-settings-install-backups').iterdir())
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0] / 'settings.py').read_text(), '# previous installation\n')


if __name__ == '__main__':
    unittest.main()
