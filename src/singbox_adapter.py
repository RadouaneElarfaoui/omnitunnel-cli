#!/usr/bin/env python3
import os
import json
import shutil
import subprocess
import configparser

def find_singbox_binary():
    """Locate sing-box binary in PATH or local ./bin directory."""
    binary_in_path = shutil.which("sing-box")
    if binary_in_path:
        return binary_in_path

    from src.paths import SINGBOX_BIN_LOCAL
    possible_paths = [
        "/usr/bin/sing-box",
        "/usr/local/bin/sing-box",
        SINGBOX_BIN_LOCAL
    ]
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None

def generate_singbox_config(config_input, socks_port=1080, tun_interface="tun0", output_mode="tun",
                           socks_in_port=1081, http_in_port=8080) -> dict:
    """
    Generate sing-box 1.12+ compatible JSON configuration dictionary using DoH (DNS-over-HTTPS).
    DoH runs over TCP/HTTPS, ensuring 100% compatibility with OpenSSH SOCKS5 proxies.

    Proxy mode multi-instance: inbounds (socks_in_port/http_in_port) and the
    socks-out upstream (socks_port) can be overridden via args or
    OMNI_SSH_SOCKS_PORT / OMNI_SOCKS_IN_PORT / OMNI_HTTP_IN_PORT env.
    """
    if isinstance(config_input, configparser.ConfigParser):
        config_dict = {s: dict(config_input[s]) for s in config_input.sections()}
    elif isinstance(config_input, dict):
        config_dict = config_input
    else:
        config_dict = {}

    # Extract SOCKS server port if specified in config
    if "ssh" in config_dict and "socks_port" in config_dict["ssh"]:
        try:
            socks_port = int(config_dict["ssh"]["socks_port"])
        except ValueError:
            pass
    # Env overrides (orchestrator allocates per-instance free ports)
    try:
        from src.ports import get_env_port, find_free_port, is_port_free as _free
        if os.environ.get("OMNI_SSH_SOCKS_PORT"):
            socks_port = get_env_port("OMNI_SSH_SOCKS_PORT", socks_port)
        if os.environ.get("OMNI_SOCKS_IN_PORT"):
            socks_in_port = get_env_port("OMNI_SOCKS_IN_PORT", socks_in_port)
        if os.environ.get("OMNI_HTTP_IN_PORT"):
            http_in_port = get_env_port("OMNI_HTTP_IN_PORT", http_in_port)
        # +1 until free for inbounds so parallel proxies don't collide.
        # Keep them distinct from each other and from the ssh -D port.
        if output_mode == "socks":
            socks_port = int(socks_port)
            socks_in_port = int(socks_in_port)
            http_in_port = int(http_in_port)
            used = {socks_port}
            if socks_in_port in used or not _free(socks_in_port):
                start = socks_in_port + 1 if socks_in_port in used else socks_in_port
                socks_in_port = find_free_port(start)
            used.add(socks_in_port)
            if http_in_port in used or not _free(http_in_port):
                start = http_in_port
                while start in used:
                    start += 1
                http_in_port = find_free_port(start)
    except Exception:
        pass

    # Log level: 'info' to debug, 'warn' (default) to reduce noise
    log_level = "warn"
    if "engine" in config_dict and "singbox_log_level" in config_dict["engine"]:
        candidate = str(config_dict["engine"]["singbox_log_level"]).strip().lower()
        if candidate in ("info", "debug", "warn", "error"):
            log_level = candidate

    # Inbounds depend on output mode
    if output_mode == "socks":
        inbounds = [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": "0.0.0.0",
                "listen_port": int(socks_in_port)
            },
            {
                "type": "http",
                "tag": "http-in",
                "listen": "0.0.0.0",
                "listen_port": int(http_in_port)
            }
        ]
    else:
        inbounds = [tun_inbound(tun_interface)]

    return build_base_singbox(
        log_level=log_level,
        detour_tag="socks-out",
        inbounds=inbounds,
        outbounds=[
            {
                "type": "socks",
                "tag": "socks-out",
                "server": "127.0.0.1",
                "server_port": socks_port
            },
            direct_outbound()
        ],
    )

def tun_inbound(tun_interface="tun0") -> dict:
    """Shared TUN inbound block (DoH DNS runs over TCP/HTTPS through it)."""
    return {
        "type": "tun",
        "tag": "tun-in",
        "interface_name": tun_interface,
        "address": ["172.19.0.1/30"],
        "auto_route": True,
        "strict_route": True,
        "stack": "mixed"
    }


def direct_outbound() -> dict:
    return {"type": "direct", "tag": "direct-out"}


def build_base_singbox(log_level: str, detour_tag: str, inbounds: list,
                       outbounds: list) -> dict:
    """Assemble a complete sing-box 1.12+ config from shared blocks.

    Single home for the log / DoH-dns / route sections so the SSH-tunnel
    builder below and the v2ray builder (`src/v2ray_parser.py`) can't drift.
    """
    return {
        "log": {
            "level": log_level,
            "timestamp": True
        },
        "dns": {
            "servers": [
                {
                    "tag": "google-doh",
                    "type": "https",
                    "server": "8.8.8.8",
                    "server_port": 443,
                    "path": "/dns-query",
                    "detour": detour_tag
                },
                {
                    "tag": "cloudflare-doh",
                    "type": "https",
                    "server": "1.1.1.1",
                    "server_port": 443,
                    "path": "/dns-query",
                    "detour": detour_tag
                }
            ]
        },
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {
            "default_domain_resolver": "google-doh",
            "rules": [
                {
                    "action": "sniff"
                },
                {
                    "action": "hijack-dns",
                    "protocol": "dns"
                }
            ],
            "auto_detect_interface": True
        }
    }

def save_singbox_config(singbox_dict: dict, output_path: str):
    """Write sing-box configuration dictionary to a JSON file."""
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(singbox_dict, f, ensure_ascii=False, indent=2)

def validate_singbox_config(config_path: str) -> tuple:
    """Validate sing-box configuration file using 'sing-box check'."""
    binary = find_singbox_binary()
    if not binary:
        return False, "sing-box binary not found on system."

    try:
        res = subprocess.run(
            [binary, "check", "-c", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if res.returncode == 0:
            return True, "Configuration is valid."
        else:
            return False, res.stderr.strip() or res.stdout.strip()
    except Exception as e:
        return False, str(e)

def main():
    binary = find_singbox_binary()
    if binary:
        print(f"✔ Found sing-box binary at: {binary}")
    else:
        print("✕ sing-box binary not found.")

if __name__ == '__main__':
    main()
