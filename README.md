[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#requirements-and-installation)

**OmniTunnel CLI** is a powerful command-line VPN client based on SSH tunnels, V2Ray/Xray protocols, and HTTP payload injection, designed to bypass network restrictions and optimize connection security under **Linux (Ubuntu/Debian)** and **Android (Termux)**.

---

## 🚀 What's New in Version v1.1.0

*   **V2Ray / Xray / Sing-Box Protocols Support**: Parse and import share links (`vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://` / `hysteria2://`) with REALITY, uTLS, WebSocket, and gRPC.
*   **Next-Gen Sing-Box TUN Engine**: High-performance **`sing-box`** TUN interface (`tun0`) with DoH (DNS-over-HTTPS) caching and 3x–5x higher throughput.
*   **Encrypted `.ot` Profile Format**: Export and import `.ot` (OmniTunnel) custom profiles with PBKDF2-HMAC-SHA256 password protection.
*   **Centralized Session Logging**: Live console streaming and ISO-timestamped session log file (`logs/session.log`) with ANSI color stripping.
*   **System-wide Terminal Shortcut**: Instant execution anywhere via the **`ot`** terminal command.
*   **Kernel TCP BBR Optimization**: Integrated Linux Kernel TCP BBR congestion control script (`vpn/tcp_bbr.sh`).

---

## 🛠 Requirements and Installation

### 1. On Debian, Ubuntu, and Linux Mint

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev sing-box
```

### 2. On Termux (Android)

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. Downloading the Project
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🚨 Root Privilege Limits & Environment Variables

When running the VPN, superuser (root) privileges are mandatory:

1.  **Resetting `$PATH` with `sudo`**: By default, `sudo` restricts command execution paths (the `secure_path` directive in `/etc/sudoers`). To prevent the startup script from failing to find your local utilities (`bin/redsocks`, `bin/dns2socks`), always run the environment from the root of the project.
2.  **Administrative Rights Required (Root)**: Orchestrating global routing flows, opening low-level descriptors, and configuring iptables NAT rules require being a superuser (Root). On Android (Termux), the device must imperatively be rooted.

---

## 🖥 Usage (Recommended Method - CLI Menu Mode)

The interactive Python script **`menu.py`** allows you to configure and launch your VPN connection with an animated visual interface.

```bash
chmod +x menu.py runvpn.sh
sudo ./menu.py
```

### Editor and Profile Management
Just like the HTTP Custom application on Android, configure your tunnels and profiles with precision:

| Main Menu | Editing SSH Parameters |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| Profile Management (Save/Load) |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

### 📦 Sharing Profiles (.ot Format)

OmniTunnel CLI includes built-in support for exporting and importing `.ot` (OmniTunnel) profile files to easily share configurations (SSH, Payloads, Proxy IPs, and SNI hosts) with other users.

- Optional **PBKDF2-HMAC-SHA256** password encryption.
- Direct management from `./menu.py` or command line:
  ```bash
  # Export active config to .ot
  python3 src/omni_profile.py export -i cfgs/settings.ini -o MyProfile.ot --name "MyServer" --password "secret"

  # Import .ot file to settings.ini
  python3 src/omni_profile.py import -i MyProfile.ot -o cfgs/settings.ini --password "secret"
  ```

---

## ⚙️ Manual Configuration (Advanced / Headless)

If you prefer configuring the VPN manually without using the interactive interface, edit the [cfgs/settings.ini](cfgs/settings.ini) file:

### Supported connection modes (`connection_mode`):
*   `mode 0`: **Direct SSH** — Raw SSH tunnel without intermediaries.
*   `mode 1`: **Payload Only** — Injection of custom HTTP headers via proxy.
*   `mode 2`: **SNI Only** — DPI evasion via SSL/TLS SNI (Server Name Indication) spoofing.
*   `mode 3`: **Payload + SNI** — Maximum masking level (HTTP Payload traversing a transparent SSL tunnel).

Once configurations are applied, launch the background agent directly:
```bash
sudo ./runvpn.sh
```

---

## 📊 Diagnostics & Connection Logs

Once connected, traffic is established and events are displayed in real-time in your console:

![Successful connection logs](docs/images/connection_logs.png)

> **Stopping the VPN**: To cleanly shut down all network tunnels and restore your operating system's default routing table, simply press `Ctrl + C`.

---

## 📄 License
This project is distributed under the permissive **Apache-2.0** license.
