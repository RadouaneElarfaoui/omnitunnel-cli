#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ssh_parser import (
    parse_ssh_uri,
    ssh_config_to_uri,
    parse_share_link,
)


class TestSshParser(unittest.TestCase):
    def test_minimal_direct(self):
        cfg, remark = parse_ssh_uri("ssh://alice:s3cr3t@vps.example.com:22#MyVPS")
        self.assertEqual(remark, "MyVPS")
        self.assertEqual(cfg["ssh"]["host"], "vps.example.com")
        self.assertEqual(cfg["ssh"]["port"], "22")
        self.assertEqual(cfg["ssh"]["username"], "alice")
        self.assertEqual(cfg["ssh"]["password"], "s3cr3t")
        self.assertEqual(cfg["mode"]["connection_mode"], "0")
        self.assertEqual(cfg["ssh"]["auth_method"], "password")
        self.assertNotIn("Payload", cfg)
        self.assertNotIn("sni", cfg)

    def test_full_fronted_profile(self):
        uri = ("ssh://bob@1.2.3.4:443?mode=3&sni=cdn.example.com"
               "&proxy=10.0.0.1:8080&payload=GET+%2F+%5Bcrlf%5D#Fronted")
        cfg, remark = parse_ssh_uri(uri)
        self.assertEqual(remark, "Fronted")
        self.assertEqual(cfg["mode"]["connection_mode"], "3")
        self.assertEqual(cfg["sni"]["server_name"], "cdn.example.com")
        self.assertEqual(cfg["Payload"]["proxyip"], "10.0.0.1")
        self.assertEqual(cfg["Payload"]["proxyport"], "8080")
        self.assertIn("[crlf]", cfg["Payload"]["payload"])

    def test_publickey_key_param(self):
        cfg, _ = parse_ssh_uri(
            "ssh://deploy@host.example.com?auth=publickey&key=%2Fhome%2Fdeploy%2F.ssh%2Fid_ed25519#K")
        self.assertEqual(cfg["ssh"]["auth_method"], "publickey")
        self.assertEqual(cfg["ssh"]["password"], "/home/deploy/.ssh/id_ed25519")

    def test_password_encoding_round_trip(self):
        cfg, _ = parse_ssh_uri("ssh://u:p%40ss%3Aw0rd@h.example.com#R")
        self.assertEqual(cfg["ssh"]["password"], "p@ss:w0rd")
        link = ssh_config_to_uri(cfg, remark="R")
        cfg2, remark2 = parse_ssh_uri(link)
        self.assertEqual(cfg2["ssh"]["password"], "p@ss:w0rd")
        self.assertEqual(remark2, "R")

    def test_export_import_round_trip(self):
        cfg = {
            "mode": {"connection_mode": "3"},
            "ssh": {"host": "vps.example.com", "port": "443",
                    "username": "bob", "password": "pw",
                    "auth_method": "password", "enable_compression": "y"},
            "Payload": {"proxyip": "10.0.0.1", "proxyport": "8080",
                        "payload": "GET / HTTP/1.1[crlf]Host: [host][crlf][crlf]"},
            "sni": {"server_name": "cdn.example.com"},
            "engine": {"engine_mode": "singbox"},
        }
        link = ssh_config_to_uri(cfg, remark="Full")
        self.assertTrue(link.startswith("ssh://"))
        cfg2, remark2 = parse_ssh_uri(link)
        self.assertEqual(remark2, "Full")
        for section in ("mode", "ssh", "Payload", "sni", "engine"):
            self.assertEqual(cfg2[section], cfg[section])

    def test_defaults_omitted_but_reapplied(self):
        cfg = {"ssh": {"host": "h.example.com", "port": "22",
                       "username": "u", "password": "",
                       "auth_method": "password", "enable_compression": "n"},
               "mode": {"connection_mode": "0"},
                "engine": {"engine_mode": "singbox-lx"}}
        link = ssh_config_to_uri(cfg)
        self.assertNotIn("?", link)  # all defaults → bare link
        cfg2, _ = parse_ssh_uri(link)
        self.assertEqual(cfg2["mode"]["connection_mode"], "0")

    def test_missing_host_rejected(self):
        with self.assertRaises(ValueError):
            parse_ssh_uri("ssh://alice:pw@#R")

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            parse_ssh_uri("ssh://u@h.example.com?mode=9#R")

    def test_dispatcher(self):
        kind, data, remark = parse_share_link("ssh://u@h.example.com#R")
        self.assertEqual(kind, "ssh")
        self.assertEqual(remark, "R")
        self.assertIn("ssh", data)
        kind, data, remark = parse_share_link(
            "trojan://secret@vpn.example.com:443?sni=vpn.example.com#T")
        self.assertEqual(kind, "v2ray")
        self.assertEqual(data["type"], "trojan")


if __name__ == "__main__":
    unittest.main()
