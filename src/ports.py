#!/usr/bin/env python3
"""Central port allocation for OmniTunnel.

Single source of truth for default ports and "+1 until free" logic,
so proxy mode can run multiple instances in parallel.

Defaults:
  SSH dynamic forward (-D) : 1080
  sing-box SOCKS inbound   : 1081
  sing-box HTTP inbound    : 8080
  injector listen port     : 9008

Usage:
  from src.ports import find_free_port, allocate_proxy_ports
  port = find_free_port(1080)
"""
import os
import socket

DEFAULT_SSH_SOCKS_PORT = 1080
DEFAULT_SOCKS_IN_PORT = 1081
DEFAULT_HTTP_IN_PORT = 8080
DEFAULT_INJECTOR_PORT = 9008
MAX_PORT = 65535


def _coerce_port(value, fallback):
    try:
        p = int(value)
        if 1 <= p <= MAX_PORT:
            return p
    except (TypeError, ValueError):
        pass
    return fallback


def get_env_port(name, default):
    """Read a port from env, falling back to default if unset/invalid."""
    return _coerce_port(os.environ.get(name), default)


def is_port_free(port, host=""):
    """True if TCP port is free to bind.

    host="" binds wildcard (covers 0.0.0.0 inbounds and 127.0.0.1
    forwarders). No SO_REUSEADDR — we want a real collision check.
    """
    port = _coerce_port(port, 0)
    if not port:
        return False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def find_free_port(start, max_tries=1000, host=""):
    """Return start or the next free port (+1 until free).

    Raises OSError if nothing free in range.
    """
    start = _coerce_port(start, 0)
    if not start:
        raise ValueError(f"Invalid start port: {start!r}")
    for offset in range(max_tries + 1):
        candidate = start + offset
        if candidate > MAX_PORT:
            break
        if is_port_free(candidate, host=host):
            return candidate
    raise OSError(f"No free port found from {start} (+{max_tries})")


def _next_free(start, used, host=""):
    """Next free port >= start skipping already-allocated `used` set."""
    candidate = _coerce_port(start, 0)
    guard = 0
    while True:
        if candidate > MAX_PORT:
            raise OSError("Port range exhausted")
        if candidate not in used and is_port_free(candidate, host=host):
            used.add(candidate)
            return candidate
        candidate += 1
        guard += 1
        if guard > 2000:
            raise OSError(f"No free port found from {start}")


def allocate_proxy_ports(ssh_socks=None, socks_in=None, http_in=None,
                         injector=None):
    """Allocate 4 distinct free ports for one proxy instance.

    Any arg left as None falls back to env (OMNI_*) then defaults.
    Returns dict with keys: ssh_socks, socks_in, http_in, injector.
    """
    if ssh_socks is None:
        ssh_socks = get_env_port("OMNI_SSH_SOCKS_PORT", DEFAULT_SSH_SOCKS_PORT)
    if socks_in is None:
        socks_in = get_env_port("OMNI_SOCKS_IN_PORT", DEFAULT_SOCKS_IN_PORT)
    if http_in is None:
        http_in = get_env_port("OMNI_HTTP_IN_PORT", DEFAULT_HTTP_IN_PORT)
    if injector is None:
        injector = get_env_port("OMNI_INJECTOR_PORT", DEFAULT_INJECTOR_PORT)
    used = set()
    return {
        "ssh_socks": _next_free(_coerce_port(ssh_socks, DEFAULT_SSH_SOCKS_PORT), used),
        "socks_in": _next_free(_coerce_port(socks_in, DEFAULT_SOCKS_IN_PORT), used),
        "http_in": _next_free(_coerce_port(http_in, DEFAULT_HTTP_IN_PORT), used),
        "injector": _next_free(_coerce_port(injector, DEFAULT_INJECTOR_PORT), used),
    }
