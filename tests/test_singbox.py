#!/usr/bin/env python3
import os
import sys
import json
import unittest
import tempfile
import configparser
import shutil

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.singbox_adapter import (
    find_singbox_binary,
    generate_singbox_config,
    save_singbox_config,
    validate_singbox_config
)

class TestSingboxAdapter(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_find_singbox_binary(self):
        binary = find_singbox_binary()
        if binary:
            self.assertTrue(os.path.exists(binary))

    def test_generate_singbox_config(self):
        sample_config = {
            "mode": {"connection_mode": "3"},
            "ssh": {"host": "1.2.3.4", "port": "443"},
            "Payload": {"proxyip": "proxy.com", "proxyport": "8080"},
            "sni": {"server_name": "sni.com"}
        }

        sb_dict = generate_singbox_config(sample_config, socks_port=1080)
        self.assertIn("log", sb_dict)
        self.assertIn("dns", sb_dict)
        self.assertIn("inbounds", sb_dict)
        self.assertIn("outbounds", sb_dict)
        self.assertIn("route", sb_dict)

        # Verify tun inbound configuration
        tun_in = sb_dict["inbounds"][0]
        self.assertEqual(tun_in["type"], "tun")
        self.assertEqual(tun_in["interface_name"], "tun0")
        self.assertTrue(tun_in["auto_route"])

        # Verify SOCKS outbound configuration
        socks_out = sb_dict["outbounds"][0]
        self.assertEqual(socks_out["type"], "socks")
        self.assertEqual(socks_out["server_port"], 1080)

    def test_save_and_validate_config(self):
        binary = find_singbox_binary()
        if not binary:
            self.skipTest("sing-box binary not installed on host system.")

        sample_config = {
            "mode": {"connection_mode": "3"},
            "ssh": {"host": "1.2.3.4", "port": "443"}
        }
        sb_dict = generate_singbox_config(sample_config, socks_port=1080)
        out_file = os.path.join(self.test_dir, "singbox_test.json")

        save_singbox_config(sb_dict, out_file)
        self.assertTrue(os.path.exists(out_file))

        is_valid, msg = validate_singbox_config(out_file)
        self.assertTrue(is_valid, f"Validation failed: {msg}")

if __name__ == "__main__":
    unittest.main()
