#!/usr/bin/env python3
import os
import sys
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

def generate_singbox_config(config_input, socks_port=1080, tun_interface="tun0") -> dict:
    """
    Generate sing-box 1.12+ compatible JSON configuration dictionary using DoH (DNS-over-HTTPS).
    DoH runs over TCP/HTTPS, ensuring 100% compatibility with OpenSSH SOCKS5 proxies.
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

    # Log level: 'info' to debug, 'warn' (default) to reduce noise
    log_level = "warn"
    if "engine" in config_dict and "singbox_log_level" in config_dict["engine"]:
        candidate = str(config_dict["engine"]["singbox_log_level"]).strip().lower()
        if candidate in ("info", "debug", "warn", "error"):
            log_level = candidate

    singbox_config = {
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
                    "detour": "socks-out"
                },
                {
                    "tag": "cloudflare-doh",
                    "type": "https",
                    "server": "1.1.1.1",
                    "server_port": 443,
                    "path": "/dns-query",
                    "detour": "socks-out"
                }
            ]
        },
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": tun_interface,
                "address": ["172.19.0.1/30"],
                "auto_route": True,
                "strict_route": True,
                "stack": "mixed"
            }
        ],
        "outbounds": [
            {
                "type": "socks",
                "tag": "socks-out",
                "server": "127.0.0.1",
                "server_port": socks_port
            },
            {
                "type": "direct",
                "tag": "direct-out"
            }
        ],
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
    return singbox_config

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
