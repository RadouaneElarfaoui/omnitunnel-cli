#!/usr/bin/env python3
"""menu_edit shows SSH rows for SSH modes, v2ray rows for v2ray mode."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.menu_options as mo

BASE_SNAPSHOT = {
    'mode_name': 'x', 'engine_label': 'e', 'sb_log_level': 'warn',
    'ssh_host': 'h', 'ssh_port': '22', 'ssh_user': 'u', 'ssh_auth': 'password',
    'ssh_compress': 'n', 'proxy_ip': 'p', 'proxy_port': '8080',
    'payload': 'p', 'sni_server': 's',
    'v2ray_remark': 'R', 'v2ray_config': '/tmp/R.json',
}


class TestMenuEditModeAware(unittest.TestCase):
    def _options_for(self, mode):
        captured = {}

        def fake_run_menu(title, options, **kwargs):
            captured['options'] = options

        snap = dict(BASE_SNAPSHOT, mode=mode)
        old_run, old_snap = mo.run_menu, mo.cached_snapshot
        mo.run_menu, mo.cached_snapshot = fake_run_menu, lambda: snap
        try:
            mo.menu_edit('test')
        finally:
            mo.run_menu, mo.cached_snapshot = old_run, old_snap
        return [key for key, _, _ in captured['options']]

    def test_ssh_mode_shows_ssh_rows(self):
        keys = self._options_for('3')
        for expected in ('2', '3', '4', '5', '6', '7'):
            self.assertIn(expected, keys)

    def test_v2ray_mode_hides_ssh_rows(self):
        keys = self._options_for('v2ray')
        for ssh_row in ('4', '5', '6', '7'):
            self.assertNotIn(ssh_row, keys)
        # profile switch, re-import, engine, log stay
        for expected in ('1', '2', '3', '8', '9', '0', 'B'):
            self.assertIn(expected, keys)


if __name__ == "__main__":
    unittest.main()
