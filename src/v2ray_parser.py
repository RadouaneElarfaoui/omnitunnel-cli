#!/usr/bin/env python3
"""
V2Ray / Xray / Sing-Box URI Parser and Configuration Converter
Supports: vless://, vmess://, trojan://, ss://, hy2:// / hysteria2://
Generates warning-free sing-box 1.12+ compatible JSON configurations.
"""

import os
import sys
import json
import base64
import binascii
import urllib.parse
import configparser

def safe_b64decode(s: str) -> str:
    """Decode base64 string with automatic padding handling."""
    s = s.strip()
    s = s.replace('-', '+').replace('_', '/')
    missing_padding = len(s) % 4
    if missing_padding:
        s += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(s).decode('utf-8', errors='ignore')
    except (binascii.Error, Exception) as e:
        raise ValueError(f"Invalid base64 data: {e}")

def parse_vless(uri: str) -> tuple:
    """
    Parse vless://uuid@host:port?params#remark
    Returns (outbound_dict, remark)
    """
    parsed = urllib.parse.urlparse(uri)
    remark = urllib.parse.unquote(parsed.fragment) or "VLESS_Profile"
    uuid = parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port or 443

    params = urllib.parse.parse_qs(parsed.query)

    transport_type = params.get("type", ["tcp"])[0].lower()
    security = params.get("security", ["none"])[0].lower()
    sni = params.get("sni", params.get("host", [host]))[0]
    path = params.get("path", ["/"])[0]
    service_name = params.get("serviceName", [""])[0]
    flow = params.get("flow", [""])[0]
    fp = params.get("fp", ["chrome"])[0]

    # REALITY parameters
    pbk = params.get("pbk", [""])[0]
    sid = params.get("sid", [""])[0]

    outbound = {
        "type": "vless",
        "tag": "vless-out",
        "server": host,
        "server_port": int(port),
        "uuid": uuid
    }
    if flow:
        outbound["flow"] = flow

    # TLS / REALITY Configuration
    if security in ("tls", "reality"):
        tls_config = {
            "enabled": True,
            "server_name": sni
        }
        if security == "reality" or fp:
            tls_config["utls"] = {
                "enabled": True,
                "fingerprint": fp or "chrome"
            }
        if security == "reality" and pbk:
            tls_config["reality"] = {
                "enabled": True,
                "public_key": pbk,
                "short_id": sid
            }
        outbound["tls"] = tls_config

    # Transport Configuration
    if transport_type == "ws":
        host_header = params.get("host", [sni])[0]
        outbound["transport"] = {
            "type": "ws",
            "path": urllib.parse.unquote(path),
            "headers": {"Host": host_header}
        }
    elif transport_type == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": service_name
        }
    elif transport_type == "http":
        outbound["transport"] = {
            "type": "http",
            "path": urllib.parse.unquote(path)
        }

    return outbound, remark

def parse_vmess(uri: str) -> tuple:
    """
    Parse vmess://base64_json
    Returns (outbound_dict, remark)
    """
    raw_payload = uri[8:]
    try:
        decoded_str = safe_b64decode(raw_payload)
        data = json.loads(decoded_str)
    except (json.JSONDecodeError, ValueError, Exception) as e:
        raise ValueError(f"Invalid VMess URI: failed to decode payload: {e}")
    remark = data.get("ps", "VMess_Profile")
    host = data.get("add", "")
    port = int(data.get("port", 443))
    uuid = data.get("id", "")
    security = data.get("scy", "auto")
    net = data.get("net", "tcp").lower()
    path = data.get("path", "/")
    tls_mode = data.get("tls", "").lower()
    sni = data.get("sni", data.get("host", host))

    outbound = {
        "type": "vmess",
        "tag": "vmess-out",
        "server": host,
        "server_port": port,
        "uuid": uuid,
        "security": security
    }

    if tls_mode in ("tls", "1"):
        outbound["tls"] = {
            "enabled": True,
            "server_name": sni
        }

    if net == "ws":
        host_header = data.get("host", sni)
        outbound["transport"] = {
            "type": "ws",
            "path": path,
            "headers": {"Host": host_header}
        }
    elif net == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": path
        }

    return outbound, remark

def parse_trojan(uri: str) -> tuple:
    """
    Parse trojan://password@host:port?params#remark
    Returns (outbound_dict, remark)
    """
    parsed = urllib.parse.urlparse(uri)
    remark = urllib.parse.unquote(parsed.fragment) or "Trojan_Profile"
    password = parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port or 443

    params = urllib.parse.parse_qs(parsed.query)

    transport_type = params.get("type", ["tcp"])[0].lower()
    sni = params.get("sni", params.get("host", [host]))[0]
    path = params.get("path", ["/"])[0]

    outbound = {
        "type": "trojan",
        "tag": "trojan-out",
        "server": host,
        "server_port": int(port),
        "password": password,
        "tls": {
            "enabled": True,
            "server_name": sni
        }
    }

    if transport_type == "ws":
        outbound["transport"] = {
            "type": "ws",
            "path": urllib.parse.unquote(path),
            "headers": {"Host": sni}
        }
    elif transport_type == "grpc":
        service_name = params.get("serviceName", [""])[0]
        outbound["transport"] = {
            "type": "grpc",
            "service_name": service_name
        }

    return outbound, remark

def parse_shadowsocks(uri: str) -> tuple:
    """
    Parse ss://base64(method:password)@host:port#remark or ss://method:password@host:port#remark
    Returns (outbound_dict, remark)
    """
    parsed = urllib.parse.urlparse(uri)
    remark = urllib.parse.unquote(parsed.fragment) or "Shadowsocks_Profile"
    host = parsed.hostname or ""
    port = parsed.port or 8388

    if parsed.username and parsed.password:
        method = parsed.username
        password = parsed.password
    elif parsed.username:
        decoded_userinfo = safe_b64decode(parsed.username)
        if ":" in decoded_userinfo:
            method, password = decoded_userinfo.split(":", 1)
        else:
            method, password = "aes-256-gcm", decoded_userinfo
    else:
        # Check if entire authority is base64 encoded (SIP002 / old format)
        raw_auth = uri[5:].split("#")[0]
        if "@" in raw_auth:
            b64_userinfo, host_port = raw_auth.split("@", 1)
            decoded_userinfo = safe_b64decode(b64_userinfo)
            if ":" in decoded_userinfo:
                method, password = decoded_userinfo.split(":", 1)
            else:
                method, password = "aes-256-gcm", decoded_userinfo
            if ":" in host_port:
                host, port_str = host_port.split(":", 1)
                port = int(port_str)
        else:
            decoded_all = safe_b64decode(raw_auth)
            # format method:password@host:port
            if "@" in decoded_all:
                userinfo, host_port = decoded_all.split("@", 1)
                method, password = userinfo.split(":", 1)
                host, port_str = host_port.split(":", 1)
                port = int(port_str)
            else:
                method, password = "aes-256-gcm", "password"

    outbound = {
        "type": "shadowsocks",
        "tag": "ss-out",
        "server": host,
        "server_port": int(port),
        "method": method,
        "password": password
    }

    return outbound, remark

def parse_hysteria2(uri: str) -> tuple:
    """
    Parse hy2://password@host:port?params#remark or hysteria2://...
    Returns (outbound_dict, remark)
    """
    parsed = urllib.parse.urlparse(uri)
    remark = urllib.parse.unquote(parsed.fragment) or "Hysteria2_Profile"
    password = parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port or 443

    params = urllib.parse.parse_qs(parsed.query)

    sni = params.get("sni", [host])[0]
    insecure = params.get("insecure", ["0"])[0] in ("1", "true")
    obfs_type = params.get("obfs", [""])[0]
    obfs_password = params.get("obfs-password", [""])[0]

    outbound = {
        "type": "hysteria2",
        "tag": "hy2-out",
        "server": host,
        "server_port": int(port),
        "password": password,
        "tls": {
            "enabled": True,
            "server_name": sni,
            "insecure": insecure
        }
    }

    if obfs_type and obfs_password:
        outbound["obfs"] = {
            "type": obfs_type,
            "password": obfs_password
        }

    return outbound, remark

def parse_v2ray_uri(uri: str) -> tuple:
    """
    Universal parser for any V2Ray / Xray / Sing-box share URI.
    Returns (outbound_dict, remark)
    """
    uri = uri.strip()
    if uri.startswith("vless://"):
        return parse_vless(uri)
    elif uri.startswith("vmess://"):
        return parse_vmess(uri)
    elif uri.startswith("trojan://"):
        return parse_trojan(uri)
    elif uri.startswith("ss://"):
        return parse_shadowsocks(uri)
    elif uri.startswith("hy2://") or uri.startswith("hysteria2://"):
        return parse_hysteria2(uri)
    else:
        raise ValueError(f"Unsupported URI protocol scheme: {uri[:10]}")

def generate_v2ray_singbox_config(outbound_dict: dict, tun_interface="tun0") -> dict:
    """
    Wrap parsed outbound dictionary into a complete, warning-free sing-box 1.12+ JSON config.
    """
    # Ensure outbound has a tag
    if "tag" not in outbound_dict:
        outbound_dict["tag"] = "proxy-out"

    log_level = "warn"
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.menu_common import read_config, status_snapshot
        candidate = status_snapshot(read_config())['sb_log_level'].strip().lower()
        if candidate in ("info", "debug", "warn", "error"):
            log_level = candidate
    except Exception:
        pass

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
                    "detour": outbound_dict["tag"]
                },
                {
                    "tag": "cloudflare-doh",
                    "type": "https",
                    "server": "1.1.1.1",
                    "server_port": 443,
                    "path": "/dns-query",
                    "detour": outbound_dict["tag"]
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
            outbound_dict,
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

if __name__ == '__main__':
    if len(sys.argv) > 1:
        uri = sys.argv[1]
        try:
            outbound, remark = parse_v2ray_uri(uri)
            cfg = generate_v2ray_singbox_config(outbound)
            print(f"✔ Parsed Remark: {remark}")
            print(json.dumps(cfg, indent=2))
        except Exception as e:
            print(f"✕ Parsing error: {e}")
            sys.exit(1)
    else:
        print("Usage: python3 src/v2ray_parser.py <vless://|vmess://|trojan://|ss://|hy2://>")
