#!/usr/bin/env python3
import os
import sys
import json
import base64
import unittest
import subprocess

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.v2ray_parser import (
    parse_vless,
    parse_vmess,
    parse_trojan,
    parse_shadowsocks,
    parse_hysteria2,
    parse_v2ray_uri,
    generate_v2ray_singbox_config
)
from src.singbox_adapter import find_singbox_binary

class TestV2RayParser(unittest.TestCase):

    def setUp(self):
        self.singbox_bin = find_singbox_binary()

    def validate_with_singbox(self, config_dict):
        if not self.singbox_bin:
            self.skipTest("sing-box binary not installed.")
        temp_file = "/tmp/test_v2ray_singbox.json"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)
        res = subprocess.run(
            [self.singbox_bin, "check", "-c", temp_file],
            capture_output=True,
            text=True
        )
        if os.path.exists(temp_file):
            os.remove(temp_file)
        self.assertEqual(res.returncode, 0, f"sing-box check failed: {res.stderr}")

    def test_parse_vless_tls_ws(self):
        uri = "vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@vps.example.com:443?type=ws&security=tls&path=%2Fvless-ws&sni=vps.example.com#VLESS_Test"
        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "VLESS_Test")
        self.assertEqual(outbound["type"], "vless")
        self.assertEqual(outbound["server"], "vps.example.com")
        self.assertEqual(outbound["server_port"], 443)
        self.assertTrue(outbound["tls"]["enabled"])
        self.assertEqual(outbound["transport"]["type"], "ws")
        self.assertEqual(outbound["transport"]["path"], "/vless-ws")

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

    def test_parse_vless_reality(self):
        pubkey_b64 = base64.urlsafe_b64encode(b'12345678901234567890123456789012').decode().rstrip('=')
        uri = f"vless://a1b2c3d4-e5f6-7890-abcd-ef1234567890@1.2.3.4:443?type=tcp&security=reality&sni=cdn.example.com&pbk={pubkey_b64}&sid=123456&fp=chrome#REALITY_Test"
        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "REALITY_Test")
        self.assertEqual(outbound["type"], "vless")
        self.assertTrue(outbound["tls"]["enabled"])
        self.assertTrue(outbound["tls"]["reality"]["enabled"])
        self.assertEqual(outbound["tls"]["reality"]["public_key"], pubkey_b64)

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

    def test_parse_vmess(self):
        vmess_data = {
            "v": "2",
            "ps": "VMess_Test",
            "add": "vmess.example.com",
            "port": "443",
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": "vmess.example.com",
            "path": "/vmess-path",
            "tls": "tls",
            "sni": "vmess.example.com"
        }
        b64_json = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        uri = f"vmess://{b64_json}"

        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "VMess_Test")
        self.assertEqual(outbound["type"], "vmess")
        self.assertEqual(outbound["server"], "vmess.example.com")
        self.assertEqual(outbound["uuid"], "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        self.assertTrue(outbound["tls"]["enabled"])

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

    def test_parse_trojan(self):
        uri = "trojan://secretpassword@trojan.example.com:443?type=ws&sni=trojan.example.com&path=%2Ftrojan-ws#Trojan_Test"
        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "Trojan_Test")
        self.assertEqual(outbound["type"], "trojan")
        self.assertEqual(outbound["password"], "secretpassword")
        self.assertTrue(outbound["tls"]["enabled"])

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

    def test_parse_shadowsocks(self):
        uri = "ss://YWVzLTI1Ni1nY206c2VjcmV0cGFzc3dvcmQ=@ss.example.com:8388#Shadowsocks_Test"
        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "Shadowsocks_Test")
        self.assertEqual(outbound["type"], "shadowsocks")
        self.assertEqual(outbound["method"], "aes-256-gcm")
        self.assertEqual(outbound["password"], "secretpassword")

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

    def test_parse_hysteria2(self):
        uri = "hy2://secretpass@hy2.example.com:443?sni=hy2.example.com&insecure=1#Hysteria2_Test"
        outbound, remark = parse_v2ray_uri(uri)
        self.assertEqual(remark, "Hysteria2_Test")
        self.assertEqual(outbound["type"], "hysteria2")
        self.assertEqual(outbound["password"], "secretpass")
        self.assertTrue(outbound["tls"]["insecure"])

        cfg = generate_v2ray_singbox_config(outbound)
        self.validate_with_singbox(cfg)

if __name__ == '__main__':
    unittest.main()
