#!/usr/bin/env python3
"""
VayDNS transport — the `vaydns://` counterpart to `ssh_parser.py`.

A vaydns profile describes N `vaydns-client` processes, each exposing a
local SSH backend over a DNS-tunneled transport:

    ./vaydns-client -tcp 8.8.8.8:53 -pubkey-file server.pub \\
        -domain vay.krel.qzz.io -listen 127.0.0.1:2222

OmniTunnel manages the whole lifecycle: it allocates N free listen ports
(count + auto), spawns one client per port, and generates a sing-box
config with one `ssh` outbound per backend behind a single balancing
group, so traffic spreads across all instances.

 balancing group:
    `type: loadbalance` is a brand-new upstream PR (post-1.14.1: strategies
    `round-robin`/`least-connections`/`source-hash`/`consistent-hash` — note
    hyphens, not `round_robin`), so no released binary — including
    sing-box-lx 1.14.1 — decodes it (probed: `unknown outbound type`).
    The lx fork instead extends `urltest` with `mode: round_robin` plus a
    `balancer` (pool/sticky_hash), which is what we emit: true per-connection
    rotation over all backends. If the fork ever rebases onto a `loadbalance`
    type, only `balance_group_outbound()` needs to change.

Format:
    vaydns://username:password@domain?params#Remark

Query params (all optional):
    tcp         DNS transport endpoint host:port (default: 8.8.8.8:53)
    pubkey-file path to server.pub (copied into cfgs/vaydns/ on import)
    instances   backend count 1..16 (default: 2)

The SSH userinfo is the SAME credential as the ssh flow — importing a
vaydns:// link writes it into the shared [ssh] username/password fields,
and the generated ssh outbounds authenticate with those exact values.

`.ot` section layout:
    [mode]    connection_mode = vaydns
    [ssh]     username / password (reused, see above)
    [vaydns]  domain / tcp / pubkey_file / instances
"""

import os
import sys
import glob
import shutil
import signal
import subprocess
import urllib.parse
import configparser

DEFAULT_TCP = "8.8.8.8:53"
DEFAULT_INSTANCES = 2
MAX_INSTANCES = 16
DEFAULT_BASE_PORT = 2222
LISTEN_HOST = "127.0.0.1"

BALANCE_TAG = "vaydns-balance"
BALANCE_GROUP_TYPE = "urltest"  # + round_robin mode: the fork's loadbalancer
BALANCE_URL = "https://www.gstatic.com/generate_204"
BALANCE_INTERVAL = "1m"

PIDFILE_PATTERN = "/tmp/omnitunnel-vaydns-*.pid"


def is_vaydns_uri(uri: str) -> bool:
    return uri.strip().lower().startswith("vaydns://")


def _parse_instances(raw, default=DEFAULT_INSTANCES) -> int:
    try:
        n = int(str(raw).strip() or default)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid instances={raw!r} (expected 1..{MAX_INSTANCES})")
    if not 1 <= n <= MAX_INSTANCES:
        raise ValueError(f"Invalid instances={n} (expected 1..{MAX_INSTANCES})")
    return n


def parse_vaydns_uri(uri: str) -> tuple:
    """Parse a vaydns:// share link.

    Returns (config_dict, remark) where config_dict uses the unified `.ot`
    section layout (mode / ssh / vaydns). The pubkey-file path is stored
    verbatim — the importer copies the file into cfgs/vaydns/.
    """
    raw = uri.strip()
    if not is_vaydns_uri(raw):
        raise ValueError(f"Not a vaydns:// share link: {raw[:16]!r}")
    parsed = urllib.parse.urlparse(raw)
    remark = urllib.parse.unquote(parsed.fragment) or "VayDNS_Profile"

    domain = parsed.hostname or ""
    if not domain:
        raise ValueError("vaydns:// link is missing a domain")
    username = urllib.parse.unquote(parsed.username or "")
    password = urllib.parse.unquote(parsed.password or "")

    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def _one(name, default=""):
        vals = params.get(name, [default])
        return vals[0] if vals else default

    tcp = _one("tcp", DEFAULT_TCP).strip() or DEFAULT_TCP
    if ":" not in tcp:
        raise ValueError(f"Invalid tcp={tcp!r} (expected host:port)")
    pubkey_file = _one("pubkey-file", "").strip()
    instances = _parse_instances(_one("instances", DEFAULT_INSTANCES))

    config_dict = {
        "mode": {"connection_mode": "vaydns"},
        "ssh": {"username": username, "password": password},
        "vaydns": {
            "domain": domain,
            "tcp": tcp,
            "pubkey_file": pubkey_file,
            "instances": str(instances),
        },
    }
    return config_dict, remark


def _as_dict(config_input) -> dict:
    if isinstance(config_input, configparser.ConfigParser):
        return {s: dict(config_input[s]) for s in config_input.sections()}
    if isinstance(config_input, dict):
        return config_input
    return {}


def vaydns_config_to_uri(config_input, remark: str = "") -> str:
    """Build a vaydns:// share link from a ConfigParser or `.ot` dict.

    SSH creds come from the shared [ssh] section (same flow); transport
    fields from [vaydns]. Defaults are omitted; the parser re-applies them.
    """
    cfg = _as_dict(config_input)
    vay = cfg.get("vaydns", {})
    domain = str(vay.get("domain", "")).strip()
    if not domain or domain in ("None", "—"):
        raise ValueError("Cannot share: VayDNS domain is not configured")
    tcp = str(vay.get("tcp", DEFAULT_TCP)).strip() or DEFAULT_TCP
    pubkey_file = str(vay.get("pubkey_file", "")).strip()
    instances = _parse_instances(vay.get("instances", DEFAULT_INSTANCES))

    ssh = cfg.get("ssh", {})
    user = str(ssh.get("username", "")).strip()
    password = str(ssh.get("password", ""))
    netloc_user = urllib.parse.quote(user, safe="") if user else ""
    if password:
        netloc_user += ":" + urllib.parse.quote(password, safe="")
    netloc = (netloc_user + "@" if netloc_user else "") + domain

    query = []
    if tcp != DEFAULT_TCP:
        query.append(f"tcp={urllib.parse.quote(tcp, safe='')}")
    if pubkey_file and pubkey_file not in ("None", "—"):
        query.append(f"pubkey-file={urllib.parse.quote(pubkey_file, safe='')}")
    if instances != DEFAULT_INSTANCES:
        query.append(f"instances={instances}")

    link = "vaydns://" + netloc
    if query:
        link += "?" + "&".join(query)
    frag = (remark or "").strip()
    if frag:
        link += "#" + urllib.parse.quote(frag, safe="")
    return link


# ---- binary --------------------------------------------------------------

def find_vaydns_binary():
    """Locate vaydns-client in PATH, local bin/, or /usr/local/bin."""
    found = shutil.which("vaydns-client")
    if found:
        return found
    try:
        from src.paths import PROJECT_DIR
        candidates = [
            os.path.join(PROJECT_DIR, "bin", "vaydns-client"),
            "/usr/local/bin/vaydns-client",
        ]
    except Exception:
        candidates = ["/usr/local/bin/vaydns-client"]
    for path in candidates:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None


VAYDNS_INSTALL_HINT = (
    "vaydns-client binary not found — install it, then retry "
    "(expected on PATH as `vaydns-client`)."
)


# ---- ports ----------------------------------------------------------------

def allocate_vaydns_ports(count, base=None) -> list:
    """Allocate `count` distinct free 127.0.0.1 listen ports, +1 until free."""
    from src.ports import find_free_port, get_env_port
    if base is None:
        base = get_env_port("OMNI_VAYDNS_BASE_PORT", DEFAULT_BASE_PORT)
    n = _parse_instances(count)
    ports = []
    start = int(base)
    for _ in range(n):
        port = find_free_port(start)
        ports.append(port)
        start = port + 1
    return ports


# ---- client lifecycle ------------------------------------------------------

def build_client_cmd(binary, tcp, pubkey_file, domain, listen_port) -> list:
    """Argument vector for one vaydns-client instance (mirrors its CLI)."""
    return [
        binary,
        "-tcp", tcp,
        "-pubkey-file", pubkey_file,
        "-domain", domain,
        "-listen", f"{LISTEN_HOST}:{listen_port}",
    ]


def _pidfile(port) -> str:
    return f"/tmp/omnitunnel-vaydns-{port}.pid"


def spawn_clients(binary, tcp, pubkey_file, domain, ports) -> list:
    """Start one detached vaydns-client per listen port. Returns Popen list.

    Processes are daemonized (own session, stdio to DEVNULL) so they
    outlive the spawner; PIDs go to /tmp pidfiles for `stop_clients`.
    """
    procs = []
    for port in ports:
        cmd = build_client_cmd(binary, tcp, pubkey_file, domain, port)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            with open(_pidfile(port), "w", encoding="utf-8") as f:
                f.write(str(proc.pid))
        except OSError:
            pass
        procs.append(proc)
    return procs


def stop_clients(ports=None):
    """Kill vaydns-client processes via pidfiles (all when ports is None)."""
    if ports is None:
        pidfiles = glob.glob(PIDFILE_PATTERN)
    else:
        pidfiles = [_pidfile(p) for p in ports]
    for pidfile in pidfiles:
        try:
            with open(pidfile, encoding="utf-8") as f:
                pid = int(f.read().strip())
            try:
                # own session at spawn → group-kill reaps orphaned children too
                os.killpg(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
        except (OSError, ValueError):
            pass
        try:
            os.remove(pidfile)
        except OSError:
            pass


# ---- sing-box config -------------------------------------------------------

def ssh_backend_outbound(tag, listen_port, username, password) -> dict:
    """One sing-box ssh outbound dialing a local vaydns-client backend."""
    return {
        "type": "ssh",
        "tag": tag,
        "server": LISTEN_HOST,
        "server_port": int(listen_port),
        "user": username,
        "password": password,
    }


def balance_group_outbound(tags) -> dict:
    """True round-robin rotation over the backend tags (see module docstring).

    pool covers every backend (small-N: all health-checked each interval);
    stickiness off so connections actually spread instead of pinning.
    """
    return {
        "type": BALANCE_GROUP_TYPE,
        "tag": BALANCE_TAG,
        "outbounds": list(tags),
        "url": BALANCE_URL,
        "interval": BALANCE_INTERVAL,
        "mode": "round_robin",
        "balancer": {
            "pool": len(tags),
            "sticky_hash": ["none"],
        },
    }


def generate_vaydns_singbox_config(username, password, listen_ports,
                                   output_mode="tun", socks_in_port=1081,
                                   http_in_port=8080, tun_interface="tun0",
                                   log_level="warn") -> dict:
    """Full sing-box config: N ssh backends behind one balancing group.

    Inbounds follow the runtime output mode (reuse apply_output_mode);
    route.final and the DoH detour both point at the balance group so
    everything, including DNS, rides the tunnel.
    """
    from src.singbox_adapter import (
        build_base_singbox, direct_outbound, apply_output_mode,
    )
    tags = [f"vaydns-ssh-{i + 1}" for i in range(len(listen_ports))]
    outbounds = [
        ssh_backend_outbound(tag, port, username, password)
        for tag, port in zip(tags, listen_ports)
    ]
    outbounds.append(balance_group_outbound(tags))
    outbounds.append(direct_outbound())
    cfg = build_base_singbox(
        log_level=log_level,
        detour_tag=BALANCE_TAG,
        inbounds=[],
        outbounds=outbounds,
    )
    cfg["route"]["final"] = BALANCE_TAG
    return apply_output_mode(
        cfg, output_mode=output_mode,
        socks_in_port=socks_in_port, http_in_port=http_in_port,
        tun_interface=tun_interface,
    )


# ---- .ot helpers ------------------------------------------------------------

def store_pubkey_file(src_path, remark) -> str:
    """Copy server.pub into cfgs/vaydns/ so the profile is self-contained.

    Returns the stored path (stored in [vaydns] pubkey_file).
    """
    from src.paths import PROJECT_DIR
    from src.menu_common import clean_filename
    dest_dir = os.path.join(PROJECT_DIR, "cfgs", "vaydns")
    os.makedirs(dest_dir, exist_ok=True)
    name = clean_filename(remark) or "vaydns"
    dest = os.path.join(dest_dir, f"{name}.pub")
    shutil.copyfile(src_path, dest)
    return dest


def activate_vaydns_config(config, config_dict):
    """Point an active config at a vaydns profile (merge, keep [ssh] host).

    Unlike v2ray activation, SSH sections are KEPT — the backends reuse
    the ssh flow's username/password. Only the credential fields are
    overwritten from the link; host/port stay untouched (unused here).
    """
    for section, values in config_dict.items():
        if not isinstance(values, dict):
            continue
        if not config.has_section(section):
            config.add_section(section)
        for key, val in values.items():
            if section == "ssh" and key in ("host", "port"):
                continue
            config.set(section, key, str(val))
    return config


def _cli_up(args) -> int:
    """Spawn clients from CLI flags; prints shell-evaluable PORTS/PIDS."""
    import argparse
    p = argparse.ArgumentParser(prog="vaydns.py up")
    p.add_argument("--instances", default=DEFAULT_INSTANCES)
    p.add_argument("--tcp", default=DEFAULT_TCP)
    p.add_argument("--pubkey-file", required=True)
    p.add_argument("--domain", required=True)
    p.add_argument("--base-port", default=None)
    p.add_argument("--binary", default=None)
    ns = p.parse_args(args)
    binary = ns.binary or find_vaydns_binary()
    if not binary:
        print(f"✕ {VAYDNS_INSTALL_HINT}", flush=True)
        return 1
    if not os.path.exists(ns.pubkey_file):
        print(f"✕ pubkey file not found: {ns.pubkey_file}", flush=True)
        return 1
    ports = allocate_vaydns_ports(ns.instances, base=ns.base_port)
    procs = spawn_clients(binary, ns.tcp, ns.pubkey_file, ns.domain, ports)
    print(f'VAYDNS_PORTS="{" ".join(str(x) for x in ports)}"')
    print(f'VAYDNS_PIDS="{" ".join(str(x.pid) for x in procs)}"')
    return 0


def _cli_down(args) -> int:
    """Kill clients; --ports limits to one instance's ports (parallel-safe)."""
    import argparse
    p = argparse.ArgumentParser(prog="vaydns.py down")
    p.add_argument("--ports", default="")
    ns = p.parse_args(args)
    ports = [int(x) for x in ns.ports.split() if x.strip().isdigit()]
    stop_clients(ports or None)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "up":
        sys.exit(_cli_up(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        sys.exit(_cli_down(sys.argv[2:]))
    if len(sys.argv) > 1:
        try:
            data, remark = parse_vaydns_uri(sys.argv[1])
            print(f"✔ remark: {remark}")
            import json
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"✕ Parsing error: {e}")
            sys.exit(1)
    else:
        print("Usage: python3 src/vaydns.py <vaydns://...> | up ... | down")
