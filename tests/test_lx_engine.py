#!/usr/bin/env python3
"""Tests for the sing-box-lx engine slice: xhttp parsing + engine resolution."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.singbox_adapter import (
    find_engine_binary,
    find_singbox_lx_binary,
)
from src.v2ray_parser import parse_vless, parse_v2ray_uri

XHTTP_URI = (
    "vless://e5e124a4-1111-4222-8333-123456789abc@104.18.37.127:443"
    "?encryption=none&security=tls&sni=ikfr.krel.qzz.io&fp=chrome"
    "&alpn=h2,http/1.1&type=xhttp&path=/srvl/&host=ikfr.krel.qzz.io&mode=auto#t"
)


class TestXhttpParsing(unittest.TestCase):
    def test_xhttp_flat_transport(self):
        outbound, _ = parse_vless(XHTTP_URI)
        self.assertEqual(outbound["transport"], {
            "type": "xhttp",
            "host": "ikfr.krel.qzz.io",
            "path": "/srvl/",
            "mode": "auto",
        })

    def test_xhttp_alpn(self):
        outbound, _ = parse_vless(XHTTP_URI)
        self.assertEqual(outbound["tls"]["alpn"], ["h2", "http/1.1"])

    def test_xhttp_defaults(self):
        outbound, _ = parse_v2ray_uri(
            "vless://aaaa1111-2222-4333-8444-555555555555@1.2.3.4:443"
            "?security=tls&type=xhttp#t"
        )
        self.assertEqual(outbound["transport"]["type"], "xhttp")
        self.assertEqual(outbound["transport"]["path"], "/")
        self.assertEqual(outbound["transport"]["mode"], "auto")
        self.assertNotIn("alpn", outbound.get("tls", {}))

    def test_ws_strips_h2_from_alpn(self):
        # WS upgrade requires HTTP/1.1: forwarding h2 makes CDNs negotiate
        # HTTP/2 and every dial dies with EOF.
        outbound, _ = parse_vless(
            "vless://aaaa1111-2222-4333-8444-555555555555@1.2.3.4:443"
            "?security=tls&type=ws&path=/w&alpn=h2,http/1.1#t"
        )
        self.assertEqual(outbound["tls"]["alpn"], ["http/1.1"])

    def test_xhttp_validates_on_lx_only(self):
        lx = find_singbox_lx_binary()
        if not lx:
            self.skipTest("sing-box-lx binary not installed.")
        from src.v2ray_parser import generate_v2ray_singbox_config
        outbound, _ = parse_vless(XHTTP_URI)
        cfg = generate_v2ray_singbox_config(outbound)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            path = f.name
        try:
            res = subprocess.run([lx, "check", "-c", path],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"lx check failed: {res.stderr}")
        finally:
            os.remove(path)


class TestEngineResolution(unittest.TestCase):
    def _make_fake_bin(self, tmp, name):
        p = os.path.join(tmp, name)
        with open(p, "w") as f:
            f.write("#!/bin/sh\necho fake\n")
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        return p

    def test_lx_resolves_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            lx = self._make_fake_bin(tmp, "sing-box-lx")
            sb = self._make_fake_bin(tmp, "sing-box")
            env_path = tmp + os.pathsep + os.environ.get("PATH", "")
            old = os.environ.get("PATH", "")
            os.environ["PATH"] = env_path
            try:
                self.assertEqual(find_singbox_lx_binary(), lx)
                self.assertEqual(find_engine_binary("singbox-lx"), lx)
                self.assertEqual(find_engine_binary("singbox"), sb)
                # unknown modes fall back to stock sing-box (legacy configs keep working)
                self.assertEqual(find_engine_binary("bogus"), sb)
            finally:
                os.environ["PATH"] = old

    def test_lx_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("PATH", "")
            os.environ["PATH"] = tmp
            try:
                self.assertIsNone(find_singbox_lx_binary())
                self.assertIsNone(find_engine_binary("singbox-lx"))
            finally:
                os.environ["PATH"] = old


if __name__ == "__main__":
    unittest.main()
