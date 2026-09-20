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
    allocate_vaydns_stack,
    build_client_cmd,
    build_forwarder_cmd,
    spawn_clients,
    spawn_forwarders,
    stop_clients,
    stop_forwarders,
    find_vaydns_binary,
    activate_vaydns_config,
    store_pubkey_file,
    materialize_pubkey,
    resolve_pubkey_file,
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

    def test_inline_pubkey_string(self):
        key = "dGVzdC12YXlkbnMtc2hhcmVkLWtleQ=="  # opaque shared key, NOT an SSH key
        link = ("vaydns://alice:pw@vay.krel.qzz.io?pubkey=" +
                __import__("urllib.parse", fromlist=["quote"]).quote(key, safe="") +
                "#K")
        d, remark = parse_vaydns_uri(link)
        self.assertEqual(d["vaydns"]["pubkey"], key)
        self.assertEqual(d["vaydns"]["pubkey_file"], "")
        d2, _ = parse_vaydns_uri(vaydns_config_to_uri(d, remark))
        self.assertEqual(d2, d)

    def test_resolve_pubkey(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = os.path.join(tmp, "server.pub")
            with open(real, "w", encoding="utf-8") as f:
                f.write("cmVhbC12YXlkbnMtc2hhcmVkLWtleQ==")
            # existing file wins over inline string
            got = resolve_pubkey_file(
                {"pubkey_file": real, "pubkey": "aW5saW5lLXZheWRucy1zaGFyZWQta2V5"}, "X")
            self.assertEqual(got, real)
            # inline string materializes to cfgs/vaydns/
            got = resolve_pubkey_file({"pubkey": "aW5saW5lLXZheWRucy1zaGFyZWQta2V5"}, "Test Resolve 9")
            try:
                self.assertTrue(got.endswith(".pub"))
                with open(got, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "aW5saW5lLXZheWRucy1zaGFyZWQta2V5\n")
            finally:
                os.remove(got)
            # neither → ""
            self.assertEqual(resolve_pubkey_file({}, "X"), "")
            self.assertEqual(
                resolve_pubkey_file({"pubkey_file": "/nonexistent/x.pub"}, "X"), "")

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
            finally:
                os.environ["PATH"] = old_path

    def test_find_binary_missing(self):
        from unittest import mock
        with mock.patch("shutil.which", return_value=None), \
             mock.patch("os.path.exists", return_value=False):
            self.assertIsNone(find_vaydns_binary())

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
                f.write("dGVzdC12YXlkbnMtc2hhcmVkLWtleQ==")
            dest = store_pubkey_file(src, "Test Remark 123")
            try:
                self.assertTrue(dest.endswith(".pub"))
                with open(dest, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "dGVzdC12YXlkbnMtc2hhcmVkLWtleQ==")
            finally:
                os.remove(dest)


class TestVaydnsConfig(unittest.TestCase):

    def test_shape(self):
        cfg = generate_vaydns_singbox_config("alice", "pw", [2240, 2241])
        socks_obs = [o for o in cfg["outbounds"] if o["type"] == "socks"]
        self.assertEqual(len(socks_obs), 2)
        self.assertEqual(socks_obs[0]["server"], "127.0.0.1")
        self.assertEqual(socks_obs[0]["server_port"], 2240)
        self.assertEqual(socks_obs[0]["tag"], "vaydns-socks-1")
        # no ssh creds leak into the sing-box config (auth lives in ssh -D)
        self.assertNotIn("password", json.dumps(cfg))
        groups = [o for o in cfg["outbounds"] if o["tag"] == BALANCE_TAG]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["outbounds"],
                         ["vaydns-socks-1", "vaydns-socks-2"])
        # true rotation, not lowest-latency pinning
        self.assertEqual(groups[0]["mode"], "round_robin")
        self.assertEqual(groups[0]["balancer"]["pool"], 2)
        self.assertEqual(groups[0]["balancer"]["sticky_hash"], ["none"])
        self.assertEqual(cfg["route"]["final"], BALANCE_TAG)
        self.assertEqual(cfg["dns"]["servers"][0]["detour"], BALANCE_TAG)
        # ssh backends are TCP-only: UDP must reject fast, after hijack-dns
        rules = cfg["route"]["rules"]
        self.assertEqual(rules[0], {"action": "sniff"})
        self.assertEqual(rules[-1], {"network": "udp", "action": "reject"})
        # TUN by default
        self.assertEqual(cfg["inbounds"][0]["type"], "tun")

    def test_single_instance_skips_group(self):
        cfg = generate_vaydns_singbox_config("a", "p", [2240])
        kinds = [o["type"] for o in cfg["outbounds"]]
        self.assertNotIn("urltest", kinds)
        self.assertEqual(cfg["route"]["final"], "vaydns-socks-1")
        self.assertEqual(cfg["dns"]["servers"][0]["detour"], "vaydns-socks-1")

    def test_proxy_inbounds(self):
        cfg = generate_vaydns_singbox_config(
            "a", "p", [2261], output_mode="socks",
            socks_in_port=1181, http_in_port=8180)
        kinds = sorted(o["type"] for o in cfg["inbounds"])
        self.assertEqual(kinds, ["http", "socks"])

    def test_stack_allocates_distinct(self):
        backends, socks = allocate_vaydns_stack(3, base=25000, socks_base=25100)
        self.assertEqual(len(backends), 3)
        self.assertEqual(len(socks), 3)
        self.assertEqual(len(set(backends + socks)), 6)

    def test_forwarder_cmd_password(self):
        argv, env = build_forwarder_cmd("root", 2222, 2240, "password", "s3cr3t")
        self.assertEqual(argv[:3], ["sshpass", "-e", "ssh"])
        self.assertIn("-D", argv)
        self.assertEqual(argv[argv.index("-D") + 1], "127.0.0.1:2240")
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("-p") + 1], "2222")
        self.assertIn("-N", argv)
        self.assertEqual(argv[-1], "root@127.0.0.1")
        self.assertEqual(env, {"SSHPASS": "s3cr3t"})
        # password never on the cmdline
        self.assertNotIn("s3cr3t", " ".join(argv))

    def test_forwarder_cmd_publickey(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = os.path.join(tmp, "id_ed")
            with open(key, "w", encoding="utf-8") as f:
                f.write("k")
            argv, env = build_forwarder_cmd("root", 2222, 2240, "publickey", key)
            self.assertEqual(argv[0], "ssh")
            self.assertNotIn("sshpass", argv)
            self.assertEqual(argv[argv.index("-i") + 1], key)
            self.assertIsNone(env)

    def test_forwarder_cmd_missing_auth(self):
        with self.assertRaises(ValueError):
            build_forwarder_cmd("root", 2222, 2240, "password", "")
        from unittest import mock
        with mock.patch("src.vaydns.resolve_key_file", return_value=None):
            with self.assertRaises(ValueError):
                build_forwarder_cmd("root", 2222, 2240, "publickey", "")

    def test_spawn_and_stop_forwarders_with_stub(self):
        import time
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            fake_ssh = os.path.join(tmp, "ssh")
            with open(fake_ssh, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\necho \"$@\" >> %s.args\nsleep 30\n" % fake_ssh)
            os.chmod(fake_ssh, 0o755)
            key = os.path.join(tmp, "id_ed")
            with open(key, "w", encoding="utf-8") as f:
                f.write("k")
            old_path = os.environ.get("PATH", "")
            try:
                os.environ["PATH"] = tmp + ":" + old_path
                with mock.patch("src.vaydns.resolve_key_file", return_value=key):
                    argv, env = build_forwarder_cmd("root", 2222, 26440, "publickey", "")
                self.assertEqual(argv[0], "ssh")  # resolves via PATH → stub
                procs = spawn_forwarders([(argv, env)])
                try:
                    time.sleep(0.5)
                    self.assertTrue(all(p.poll() is None for p in procs))
                    self.assertTrue(os.path.exists("/tmp/omnitunnel-vaydns-fwd-26440.pid"))
                    with open(fake_ssh + ".args", encoding="utf-8") as f:
                        logged = f.read()
                    self.assertIn("-D 127.0.0.1:26440", logged)
                finally:
                    stop_forwarders([26440])
                time.sleep(0.3)
                self.assertTrue(all(p.poll() is not None for p in procs))
            finally:
                os.environ["PATH"] = old_path

    def test_wait_for_socks_ports(self):
        import socket
        from src.vaydns import wait_for_socks_ports
        from src.ports import find_free_port
        port = find_free_port(27100)
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        try:
            # plain accept counts (no banner expected)
            self.assertEqual(wait_for_socks_ports([port], timeout=3), [])
            self.assertEqual(wait_for_socks_ports([27998], timeout=1), [27998])
        finally:
            srv.close()

    def test_wait_for_backends(self):
        import socket
        import threading
        from src.vaydns import wait_for_backends
        from src.ports import find_free_port
        port = find_free_port(27000)

        def serve_once():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            srv.settimeout(5)
            try:
                conn, _ = srv.accept()
                conn.sendall(b"SSH-2.0-test\r\n")
                conn.close()
            except OSError:
                pass
            finally:
                srv.close()

        t = threading.Thread(target=serve_once, daemon=True)
        t.start()
        self.assertEqual(wait_for_backends([port], timeout=5), [])
        # silent port (accepts, no banner) + closed port never clear
        srv2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port2 = find_free_port(port + 1)
        srv2.bind(("127.0.0.1", port2))
        srv2.listen(1)
        try:
            missing = wait_for_backends([port2, 27999], timeout=1)
            self.assertEqual(sorted(missing), sorted([port2, 27999]))
        finally:
            srv2.close()

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
