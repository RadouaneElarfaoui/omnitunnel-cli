#!/usr/bin/env python3
import os
import sys
import socket
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ports import (
    find_free_port, allocate_proxy_ports, is_port_free,
    DEFAULT_SSH_SOCKS_PORT,
)


class TestPorts(unittest.TestCase):
    def test_find_free_skips_busy(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        try:
            self.assertFalse(is_port_free(busy))
            nxt = find_free_port(busy, max_tries=50)
            self.assertNotEqual(nxt, busy)
            self.assertTrue(is_port_free(nxt))
        finally:
            s.close()

    def test_allocate_distinct(self):
        p = allocate_proxy_ports(ssh_socks=18080, socks_in=18081,
                                 http_in=18082, injector=19008)
        vals = [p["ssh_socks"], p["socks_in"], p["http_in"], p["injector"]]
        self.assertEqual(len(set(vals)), 4)
        for v in vals:
            self.assertTrue(is_port_free(v))

    def test_allocate_avoids_busy(self):
        holders = []
        try:
            for port in (18180, 18181):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", port))
                holders.append(s)
            p = allocate_proxy_ports(ssh_socks=18180, socks_in=18181,
                                     http_in=18182, injector=19108)
            self.assertNotIn(p["ssh_socks"], (18180,))
            self.assertNotIn(p["socks_in"], (18181,))
            self.assertEqual(len(set(p.values())), 4)
        finally:
            for s in holders:
                s.close()

    def test_singbox_config_uses_ports(self):
        from src.singbox_adapter import generate_singbox_config
        cfg = {"ssh": {}, "engine": {}}
        sb = generate_singbox_config(cfg, socks_port=18280, output_mode="socks",
                                     socks_in_port=18281, http_in_port=18282)
        inb = {i["tag"]: i["listen_port"] for i in sb["inbounds"]}
        self.assertEqual(sb["outbounds"][0]["server_port"], 18280)
        self.assertEqual(inb["socks-in"], 18281)
        self.assertEqual(inb["http-in"], 18282)


if __name__ == "__main__":
    unittest.main()
