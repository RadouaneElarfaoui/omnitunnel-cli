#!/usr/bin/env python3
"""
SSH share-link parser — the `ssh://` counterpart to `v2ray_parser.py`.

Unifies SSH profiles with the vless:// / trojan:// / ss:// / hy2:// workflow:
one link carries a complete tunnel profile and imports straight into the
unified `.ot` config sections.

Format:
    ssh://username[:password]@host[:port]?params#Remark

Query params (all optional):
    auth      password | publickey            (default: password)
    mode      0 | 1 | 2 | 3                   (default: 0 = direct SSH)
    sni       SNI hostname for TLS modes 2/3
    proxy     proxy_ip[:proxy_port] for HTTP payload modes 1/3
    payload   URL-encoded HTTP payload template
    key       private-key path (publickey auth; overrides userinfo password)
    compress  y | n  (SSH compression, default: n)
    engine    singbox | singbox-lx | redsocks  (default: singbox-lx)

Examples:
    ssh://alice:s3cr3t@vps.example.com:22#MyVPS
    ssh://bob@1.2.3.4:443?mode=3&sni=cdn.example.com&proxy=10.0.0.1:8080&payload=GET+%2F+%5Bcrlf%5D#Fronted
    ssh://deploy@host.example.com?auth=publickey&key=%2Fhome%2Fdeploy%2F.ssh%2Fid_ed25519#DeployKey
"""

import sys
import urllib.parse
import configparser

DEFAULT_SSH_PORT = "22"
DEFAULT_AUTH = "password"
DEFAULT_MODE = "0"
DEFAULT_COMPRESS = "n"
DEFAULT_ENGINE = "singbox-lx"

_VALID_MODES = ("0", "1", "2", "3")
_VALID_AUTHS = ("password", "publickey")
_VALID_ENGINES = ("singbox", "singbox-lx", "redsocks")


def is_ssh_uri(uri: str) -> bool:
    return uri.strip().lower().startswith("ssh://")


def parse_ssh_uri(uri: str) -> tuple:
    """Parse an ssh:// share link.

    Returns (config_dict, remark) where config_dict uses the unified `.ot`
    section layout (mode / ssh / Payload / sni / engine). Optional sections
    (Payload keys, sni) are only included when the link carries them, so
    importing never wipes fields the link doesn't mention.
    """
    raw = uri.strip()
    if not is_ssh_uri(raw):
        raise ValueError(f"Not an ssh:// share link: {raw[:16]!r}")
    parsed = urllib.parse.urlparse(raw)
    remark = urllib.parse.unquote(parsed.fragment) or "SSH_Profile"

    host = parsed.hostname or ""
    if not host:
        raise ValueError("ssh:// link is missing a host")
    port = str(parsed.port or DEFAULT_SSH_PORT)
    username = urllib.parse.unquote(parsed.username or "")
    user_password = urllib.parse.unquote(parsed.password or "")

    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    def _one(name, default=""):
        vals = params.get(name, [default])
        return vals[0] if vals else default

    auth = _one("auth", DEFAULT_AUTH).strip().lower() or DEFAULT_AUTH
    if auth not in _VALID_AUTHS:
        raise ValueError(f"Invalid auth={auth!r} (expected password|publickey)")
    mode = _one("mode", DEFAULT_MODE).strip() or DEFAULT_MODE
    if mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode={mode!r} (expected 0|1|2|3)")
    compress = _one("compress", DEFAULT_COMPRESS).strip().lower() or DEFAULT_COMPRESS
    if compress not in ("y", "n"):
        raise ValueError(f"Invalid compress={compress!r} (expected y|n)")
    engine = _one("engine", DEFAULT_ENGINE).strip().lower() or DEFAULT_ENGINE
    if engine not in _VALID_ENGINES:
        raise ValueError(f"Invalid engine={engine!r} (expected singbox|singbox-lx|redsocks)")

    # publickey: `key` param is the key path; falls back to userinfo password
    # (this codebase resolves the password field as a key path for publickey).
    credential = _one("key", "") or user_password

    config_dict = {
        "mode": {"connection_mode": mode},
        "ssh": {
            "host": host,
            "port": port,
            "username": username,
            "password": credential,
            "auth_method": auth,
            "enable_compression": compress,
        },
        "engine": {"engine_mode": engine},
    }

    proxy_raw = _one("proxy", "")
    payload_tpl = _one("payload", "")
    if proxy_raw or payload_tpl:
        section = {}
        if proxy_raw:
            if ":" in proxy_raw:
                ip, pport = proxy_raw.rsplit(":", 1)
                section["proxyip"] = ip.strip()
                if pport.strip():
                    section["proxyport"] = pport.strip()
            else:
                section["proxyip"] = proxy_raw.strip()
        if payload_tpl:
            section["payload"] = payload_tpl
        if section:
            config_dict["Payload"] = section

    sni = _one("sni", "")
    if sni:
        config_dict["sni"] = {"server_name": sni}

    return config_dict, remark


def _as_dict(config_input) -> dict:
    if isinstance(config_input, configparser.ConfigParser):
        return {s: dict(config_input[s]) for s in config_input.sections()}
    if isinstance(config_input, dict):
        return config_input
    return {}


def ssh_config_to_uri(config_input, remark: str = "") -> str:
    """Build an ssh:// share link from a ConfigParser or `.ot` config dict.

    Defaults (port 22, password auth, mode 0, no compression, singbox) are
    omitted to keep links short; `parse_ssh_uri` re-applies them on import.
    """
    cfg = _as_dict(config_input)
    ssh = cfg.get("ssh", {})
    host = str(ssh.get("host", "")).strip()
    if not host or host in ("None", "—"):
        raise ValueError("Cannot share: SSH host is not configured")
    port = str(ssh.get("port", DEFAULT_SSH_PORT)).strip() or DEFAULT_SSH_PORT
    user = str(ssh.get("username", "")).strip()
    credential = str(ssh.get("password", ""))
    auth = str(ssh.get("auth_method", DEFAULT_AUTH)).strip().lower() or DEFAULT_AUTH
    compress = str(ssh.get("enable_compression", DEFAULT_COMPRESS)).strip().lower() or DEFAULT_COMPRESS
    mode = str(cfg.get("mode", {}).get("connection_mode", DEFAULT_MODE)).strip() or DEFAULT_MODE
    engine = str(cfg.get("engine", {}).get("engine_mode", DEFAULT_ENGINE)).strip().lower() or DEFAULT_ENGINE

    # netloc: user[:password]@host[:port] — key path goes to ?key= instead
    if auth == "publickey":
        netloc_user = urllib.parse.quote(user, safe="") if user else ""
        secret = ""
        key_param = credential
    else:
        netloc_user = urllib.parse.quote(user, safe="") if user else ""
        if credential:
            netloc_user += ":" + urllib.parse.quote(credential, safe="")
        key_param = ""
    netloc = (netloc_user + "@" if netloc_user else "") + host
    if port != DEFAULT_SSH_PORT:
        netloc += f":{port}"

    query = []
    if auth != DEFAULT_AUTH:
        query.append(f"auth={auth}")
    if mode != DEFAULT_MODE:
        query.append(f"mode={urllib.parse.quote(mode, safe='')}")
    if compress != DEFAULT_COMPRESS:
        query.append(f"compress={compress}")
    if engine != DEFAULT_ENGINE:
        query.append(f"engine={engine}")
    if auth == "publickey" and key_param:
        query.append(f"key={urllib.parse.quote(key_param, safe='')}")
    if "Payload" in cfg:
        ip = str(cfg["Payload"].get("proxyip", "")).strip()
        pport = str(cfg["Payload"].get("proxyport", "")).strip()
        if ip and ip not in ("None", "—"):
            proxy = ip + (f":{pport}" if pport and pport not in ("None", "—") else "")
            query.append(f"proxy={urllib.parse.quote(proxy, safe='')}")
        payload_tpl = str(cfg["Payload"].get("payload", ""))
        if payload_tpl and payload_tpl not in ("None", "—"):
            query.append(f"payload={urllib.parse.quote(payload_tpl, safe='')}")
    if "sni" in cfg:
        sni = str(cfg["sni"].get("server_name", "")).strip()
        if sni and sni not in ("None", "—"):
            query.append(f"sni={urllib.parse.quote(sni, safe='')}")

    link = "ssh://" + netloc
    if query:
        link += "?" + "&".join(query)
    frag = (remark or "").strip()
    if frag:
        link += "#" + urllib.parse.quote(frag, safe="")
    return link


def parse_share_link(uri: str) -> tuple:
    """Unified entry point for every share-link scheme.

    Returns ("ssh", config_dict, remark) for ssh:// links (config_dict in
    `.ot` section layout, ready to merge into the active profile),
    ("vaydns", config_dict, remark) for vaydns:// links (same layout,
    mode/vaydns sections), or ("v2ray", outbound_dict, remark) for
    vless/vmess/trojan/ss/hy2 links (outbound_dict in sing-box layout).
    """
    cleaned = uri.strip()
    if is_ssh_uri(cleaned):
        config_dict, remark = parse_ssh_uri(cleaned)
        return ("ssh", config_dict, remark)
    from src.vaydns import is_vaydns_uri, parse_vaydns_uri
    if is_vaydns_uri(cleaned):
        config_dict, remark = parse_vaydns_uri(cleaned)
        return ("vaydns", config_dict, remark)
    from src.v2ray_parser import parse_v2ray_uri
    outbound, remark = parse_v2ray_uri(cleaned)
    return ("v2ray", outbound, remark)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            kind, data, remark = parse_share_link(sys.argv[1])
            print(f"✔ kind: {kind}  remark: {remark}")
            import json
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"✕ Parsing error: {e}")
            sys.exit(1)
    else:
        print("Usage: python3 src/ssh_parser.py <ssh://...|vaydns://...|vless://|vmess://|trojan://|ss://|hy2://>")
