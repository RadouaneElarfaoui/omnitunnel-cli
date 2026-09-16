#!/usr/bin/env python3
import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.menu_common as mc
from src.menu_common import read_config, cached_snapshot
from src.omni_profile import export_profile_to_omni, dict_to_configparser

EXAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "cfgs", "settings.ot.example")


def _render_cache_reset():
    mc._render_cache.update({"path": None, "mtime": None, "config": None, "snapshot": None})


class TestInstanceProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = dict(os.environ)
        self._config_path = mc.CONFIG_PATH
        self._example_path = mc.CONFIG_EXAMPLE_PATH
        os.environ.pop("OMNI_PROFILE_PATH", None)
        os.environ.pop("OMNI_PROFILE_SRC", None)
        _render_cache_reset()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        mc.CONFIG_PATH = self._config_path
        mc.CONFIG_EXAMPLE_PATH = self._example_path
        _render_cache_reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snap(self, host="isolated.example.com"):
        """Copy example to tmp instance file with a custom host."""
        with open(EXAMPLE, encoding="utf-8") as f:
            meta = json.load(f)
        meta["config"]["ssh"]["host"] = host
        path = os.path.join(self.tmp, "instance.ot")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        return path

    def test_override_reads_snapshot_not_active(self):
        snap = self._snap()
        os.environ["OMNI_PROFILE_PATH"] = snap
        cfg = read_config()
        self.assertEqual(cfg.get("ssh", "host"), "isolated.example.com")

    def test_override_fail_closed_and_clobbers_nothing(self):
        bad = os.path.join(self.tmp, "bad.ot")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{torn json,,,")
        active = os.path.join(self.tmp, "active.ot")
        with open(active, "w", encoding="utf-8") as f:
            f.write("SENTINEL")
        mc.CONFIG_PATH = active
        os.environ["OMNI_PROFILE_PATH"] = bad
        cfg = read_config()
        self.assertEqual(cfg.sections(), [])
        with open(active, encoding="utf-8") as f:
            self.assertEqual(f.read(), "SENTINEL")

    def test_corrupt_active_fails_closed_without_example_clobber(self):
        active = os.path.join(self.tmp, "active.ot")
        with open(active, "w", encoding="utf-8") as f:
            f.write("not json at all")
        mc.CONFIG_PATH = active
        mc.CONFIG_EXAMPLE_PATH = EXAMPLE
        cfg = read_config()
        self.assertEqual(cfg.sections(), [])
        with open(active, encoding="utf-8") as f:
            self.assertEqual(f.read(), "not json at all")

    def test_missing_active_still_seeds_from_example(self):
        active = os.path.join(self.tmp, "active.ot")
        mc.CONFIG_PATH = active
        mc.CONFIG_EXAMPLE_PATH = EXAMPLE
        cfg = read_config()
        self.assertEqual(cfg.get("ssh", "host"), "vps.example.com")
        self.assertTrue(os.path.exists(active))

    def test_cache_switches_with_override_path(self):
        a = self._snap("host-a.example.com")
        os.environ["OMNI_PROFILE_PATH"] = a
        self.assertEqual(cached_snapshot()["ssh_host"], "host-a.example.com")
        b = self._snap("host-b.example.com")
        os.environ["OMNI_PROFILE_PATH"] = b
        self.assertEqual(cached_snapshot()["ssh_host"], "host-b.example.com")

    def test_export_atomic_no_tmp_leftover(self):
        cfg = dict_to_configparser({"ssh": {"host": "h"}})
        out = os.path.join(self.tmp, "p.ot")
        export_profile_to_omni(cfg, profile_name="p", output_path=out)
        leftovers = [f for f in os.listdir(self.tmp) if ".tmp-" in f]
        self.assertEqual(leftovers, [])
        with open(out, encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["config"]["ssh"]["host"], "h")


if __name__ == "__main__":
    unittest.main()
