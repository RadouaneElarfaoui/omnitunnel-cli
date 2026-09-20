#!/usr/bin/env python3
"""Tests for the vaydns:// transport (src/vaydns.py)."""
import configparser
import json
import os
import stat
import tempfile
import time
import unittest

from src.vaydns import (
    parse_vaydns_uri,
    vaydns_config_to_uri,
    is_vaydns_uri,
    allocate_vaydns_ports,
    build_client_cmd,
    spawn_clients,
    stop_clients,
    find_vaydns_binary,
    activate_vaydns_config,
    store_pubkey_file,
    generate_vaydns_singbox_config,
    BALANCE_TAG,
    DEFAULT_TCP,
    DEFAULT_INSTANCES,
)
from src.singbox_adapter import find_singbox_lx_binary


def _write_stub(path):
    """Fake vaydns-client: logs argv, then sleeps until killed."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n"
                f"echo \"$@\" >> {path}.args\n"
                "sleep 30\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


class TestVaydnsLink(unittest.TestCase):

    def test_full_link(self):
        d, remark = parse_vaydns_uri(
            "vaydns://alice:s3cr3t@vay.krel.qzz.io"
            "?tcp=8.8.8.8:53&pubkey-file=server.pub&instances=3#Home")
        self.assertEqual(remark, "Home")
        self.assertEqual(d["mode"]["connection_mode"], "vaydns")
        self.assertEqual(d["ssh"], {"username": "alice", "password": "s3cr3t"})
        self.assertEqual(d["vaydns"]["domain"], "vay.krel.qzz.io")
        self.assertEqual(d["vaydns"]["tcp"], "8.8.8.8:53")
        self.assertEqual(d["vaydns"]["pubkey_file"], "server.pub")
        self.assertEqual(d["vaydns"]["instances"], "3")

    def test_defaults(self):
        d, remark = parse_vaydns_uri("vaydns://bob@tun.example.com")
        self.assertEqual(remark, "VayDNS_Profile")
        self.assertEqual(d["vaydns"]["tcp"], DEFAULT_TCP)
        self.assertEqual(d["vaydns"]["instances"], str(DEFAULT_INSTANCES))
        self.assertEqual(d["vaydns"]["pubkey_file"], "")
        self.assertEqual(d["ssh"]["password"], "")

    def test_invalid(self):
        for bad in ("ssh://x@y",
                    "vaydns://?tcp=1.2.3.4:53",
                    "vaydns://u@d?instances=0",
                    "vaydns://u@d?instances=99",
                    "vaydns://u@d?instances=many",
                    "vaydns://u@d?tcp=8.8.8.8"):
            with self.assertRaises(ValueError, msg=bad):
                parse_vaydns_uri(bad)

    def test_round_trip(self):
        link = ("vaydns://alice:s3cr3t@vay.krel.qzz.io"
                "?tcp=1.1.1.1:5353&pubkey-file=%2Ftmp%2Fsrv.pub&instances=4#R")
        d, remark = parse_vaydns_uri(link)
        d2, remark2 = parse_vaydns_uri(vaydns_config_to_uri(d, remark))
        self.assertEqual(d2, d)
        self.assertEqual(remark2, remark)

    def test_export_omits_defaults(self):
        d, _ = parse_vaydns_uri("vaydns://bob@tun.example.com")
        link = vaydns_config_to_uri(d, "X")
        self.assertNotIn("tcp=", link)
        self.assertNotIn("instances=", link)
        self.assertTrue(is_vaydns_uri(link))

    def test_export_needs_domain(self):
        with self.assertRaises(ValueError):
            vaydns_config_to_uri({"vaydns": {}, "ssh": {}})


class TestVaydnsRuntime(unittest.TestCase):

    def test_allocate_ports(self):
        ports = allocate_vaydns_ports(3, base=25000)
        self.assertEqual(len(ports), 3)
        self.assertEqual(len(set(ports)), 3)
        self.assertTrue(all(p >= 25000 for p in ports))

    def test_client_cmd_mirrors_cli(self):
        cmd = build_client_cmd("/usr/bin/vaydns-client", "8.8.8.8:53",
                               "server.pub", "vay.krel.qzz.io", 2222)
        self.assertEqual(cmd, ["/usr/bin/vaydns-client", "-tcp", "8.8.8.8:53",
                               "-pubkey-file", "server.pub",
                               "-domain", "vay.krel.qzz.io",
                               "-listen", "127.0.0.1:2222"])

    def test_find_binary_respects_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "vaydns-client")
            _write_stub(stub)
            old_path = os.environ.get("PATH", "")
            try:
                os.environ["PATH"] = tmp
                self.assertEqual(find_vaydns_binary(), stub)
                os.environ["PATH"] = tempfile.mkdtemp()
                self.assertIsNone(find_vaydns_binary())
            finally:
                os.environ["PATH"] = old_path

    def test_spawn_and_stop_with_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "vaydns-client")
            _write_stub(stub)
            ports = allocate_vaydns_ports(2, base=26000)
            procs = spawn_clients(stub, "8.8.8.8:53", "srv.pub",
                                  "vay.krel.qzz.io", ports)
            try:
                time.sleep(0.5)
                self.assertTrue(all(p.poll() is None for p in procs))
                with open(stub + ".args", encoding="utf-8") as f:
                    lines = f.read().strip().splitlines()
                self.assertEqual(len(lines), 2)
                for line, port in zip(lines, ports):
                    self.assertIn(f"-listen 127.0.0.1:{port}", line)
                    self.assertIn("-domain vay.krel.qzz.io", line)
                for port in ports:
                    self.assertTrue(
                        os.path.exists(f"/tmp/omnitunnel-vaydns-{port}.pid"))
            finally:
                stop_clients(ports)
            time.sleep(0.3)
            self.assertTrue(all(p.poll() is not None for p in procs))

    def test_activate_keeps_ssh_host(self):
        cfg = configparser.ConfigParser()
        cfg.add_section("mode")
        cfg.add_section("ssh")
        cfg.set("ssh", "host", "old.example.com")
        cfg.set("ssh", "port", "22")
        d, _ = parse_vaydns_uri("vaydns://alice:pw@vay.krel.qzz.io?instances=2")
        cfg = activate_vaydns_config(cfg, d)
        self.assertEqual(cfg.get("mode", "connection_mode"), "vaydns")
        self.assertEqual(cfg.get("ssh", "host"), "old.example.com")
        self.assertEqual(cfg.get("ssh", "port"), "22")
        self.assertEqual(cfg.get("ssh", "username"), "alice")
        self.assertEqual(cfg.get("ssh", "password"), "pw")
        self.assertEqual(cfg.get("vaydns", "domain"), "vay.krel.qzz.io")

    def test_store_pubkey(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "server.pub")
            with open(src, "w", encoding="utf-8") as f:
                f.write("ssh-ed25519 AAAA test")
            dest = store_pubkey_file(src, "Test Remark 123")
            try:
                self.assertTrue(dest.endswith(".pub"))
                with open(dest, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "ssh-ed25519 AAAA test")
            finally:
                os.remove(dest)


class TestVaydnsConfig(unittest.TestCase):

    def test_shape(self):
        cfg = generate_vaydns_singbox_config("alice", "pw", [2251, 2252])
        ssh_obs = [o for o in cfg["outbounds"] if o["type"] == "ssh"]
        self.assertEqual(len(ssh_obs), 2)
        self.assertEqual(ssh_obs[0]["server"], "127.0.0.1")
        self.assertEqual(ssh_obs[0]["server_port"], 2251)
        self.assertEqual(ssh_obs[0]["user"], "alice")
        groups = [o for o in cfg["outbounds"] if o["tag"] == BALANCE_TAG]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["outbounds"],
                         ["vaydns-ssh-1", "vaydns-ssh-2"])
        # true rotation, not lowest-latency pinning
        self.assertEqual(groups[0]["mode"], "round_robin")
        self.assertEqual(groups[0]["balancer"]["pool"], 2)
        self.assertEqual(groups[0]["balancer"]["sticky_hash"], ["none"])
        self.assertEqual(cfg["route"]["final"], BALANCE_TAG)
        self.assertEqual(cfg["dns"]["servers"][0]["detour"], BALANCE_TAG)
        # TUN by default
        self.assertEqual(cfg["inbounds"][0]["type"], "tun")

    def test_proxy_inbounds(self):
        cfg = generate_vaydns_singbox_config(
            "a", "p", [2261], output_mode="socks",
            socks_in_port=1181, http_in_port=8180)
        kinds = sorted(o["type"] for o in cfg["inbounds"])
        self.assertEqual(kinds, ["http", "socks"])

    def test_validates_on_lx(self):
        lx = find_singbox_lx_binary()
        if not lx:
            self.skipTest("sing-box-lx not installed")
        import subprocess
        cfg = generate_vaydns_singbox_config("a", "p", [2271, 2272, 2273])
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump(cfg, f)
            path = f.name
        try:
            res = subprocess.run([lx, "check", "-c", path],
                                 capture_output=True, text=True, timeout=15)
            self.assertEqual(res.returncode, 0, res.stderr.strip())
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
