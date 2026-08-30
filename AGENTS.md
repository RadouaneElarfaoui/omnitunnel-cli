# AGENTS.md — OmniTunnel CLI Agent & Developer Guidelines

This document provides technical guidelines and architectural documentation for AI assistants (Google Antigravity, AGY, Claude) and developers working on **OmniTunnel CLI**.

## 🚀 Execution & Command Shortcuts

### System-wide Shortcut
- Launch via terminal shortcut:
  ```bash
  ot
  ```
- Direct menu launch:
  ```bash
  sudo ./menu.py
  ```

### Development & Maintenance Commands

* **Run Automated Test Suite**:
  ```bash
  python3 -m unittest discover -s tests -p "test_*.py" -v
  ```

* **Launch Headless VPN Engine Directly**:
  ```bash
  sudo ./runvpn.sh
  ```

* **V2Ray / Xray Share Link Converter**:
  ```bash
  # Parse share URI (vless, vmess, trojan, ss, hy2) and output sing-box 1.12+ JSON config
  python3 src/v2ray_parser.py "vless://uuid@host:port?type=ws&security=tls#Remark"
  ```

* **Export / Import `.ot` Profiles**:
  ```bash
  # Export profile to encrypted .ot format
  python3 src/omni_profile.py export -i cfgs/settings.ini -o profile.ot -n "ProfileName" --password "secret"

  # Import .ot profile to settings.ini
  python3 src/omni_profile.py import -i profile.ot -o cfgs/settings.ini --password "secret"
  ```

* **Kernel TCP BBR Optimization**:
  ```bash
  sudo bash vpn/tcp_bbr.sh
  ```

---

## 🏗 Build & Compilation Architecture

Dependencies are compiled automatically on launch by [runvpn.sh](runvpn.sh) if not pre-installed on the system:
* **Redsocks**: Compiled on the fly from [libs/redsocks.zip](libs/redsocks.zip) to `bin/redsocks`.
* **Dns2socks**: Compiled on the fly from [libs/dns2socks.zip](libs/dns2socks.zip) to `bin/dns2socks`.
* **Sing-Box TUN Engine**: Located via system `$PATH` or local `bin/sing-box` binary.

---

## 📐 Architecture Overview

OmniTunnel CLI is a high-performance Python & Shell-based VPN client utilizing custom HTTP payloads, SSL SNI spoofing, SSH-encrypted tunnels, and V2Ray/Sing-Box TUN interfaces to bypass network restrictions.

### Data & Execution Flow
1. **Interactive UI & Profile Manager**: [menu.py](menu.py) manages system-wide configurations and `.ot` profiles under `cfgs/saved/`. Active settings are stored in [cfgs/settings.ini](cfgs/settings.ini) (ignored by git for privacy).
2. **Startup Control**: [runvpn.sh](runvpn.sh) checks binary dependencies, sets signal traps (`SIGINT`/`SIGTERM`), cleans old processes, and initiates [main.py](main.py) or `singbox_proxification`.
3. **Payload Injection & SNI Proxy**: [main.py](main.py) initializes [src/tunnel.py](src/tunnel.py) listening on a dynamic local port. It formats HTTP injection headers via [src/inject.py](src/inject.py) and handles SSL/TLS handshakes with spoofed SNI hostnames.
4. **SSH SOCKS5 Forwarding**: [src/ssh.py](src/ssh.py) sets up dynamic SOCKS5 forwarding (`-CND 1080`) over SSH using `sshpass -e` and environment variables to hide credentials from process lists (`ps aux`).
5. **Sing-Box TUN Engine & DNS-over-HTTPS**: For modern High-Speed mode, [vpn/singbox_proxification](vpn/singbox_proxification) launches `sing-box` with DoH (`8.8.8.8` / `1.1.1.1` HTTPS query endpoints), creating `tun0` interface with automatic global routing.
6. **Legacy Redsocks & iptables Routing**: For legacy mode, [vpn/proxification](vpn/proxification) sets up `iptables` NAT redirection to `redsocks` and tunnels DNS via `dns2socks`.
7. **Centralized Logging System**: [src/logger.py](src/logger.py) streams formatted events to console in real-time while writing ISO-timestamped, ANSI-stripped clean logs to `logs/session.log`.
