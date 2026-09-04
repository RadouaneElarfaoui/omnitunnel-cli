# Changelog

## v1.1.1

* **Launcher visibility fix**: `.deb` now ships world-readable desktop entry + icon (`0644`) and refreshes `update-desktop-database` / `gtk-update-icon-cache` on install/remove, so OmniTunnel appears in the app menu.
* **Cwd-independent launchers**: `runvpn.sh`, `ConfMake`, `vpn/proxification`, and `main.py` use absolute `PROJECT_DIR` paths (and `PYTHONPATH`) so they work from any working directory, including the desktop launcher.
* **`otunnel` command packaged**: `/usr/local/bin/otunnel` is now included in the `.deb` and re-created by `postinst`, and is used as the desktop `Exec=` target.
* **Perm normalization**: all files under `/opt/omnitunnel-cli` are unpacked with safe `0644`/`0755`/`0755`-dir permissions regardless of source checkout modes.

## v1.1.0

* **V2Ray / Xray / Sing-Box Protocols Support**: Parse and import share links (`vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://` / `hysteria2://`) with REALITY, uTLS, WebSocket, and gRPC.
* **Next-Gen Sing-Box TUN Engine**: High-performance **`sing-box`** TUN interface (`tun0`) with DoH (DNS-over-HTTPS) caching and 3x–5x higher throughput.
* **Encrypted `.ot` Profile Format**: Export and import `.ot` (OmniTunnel) custom profiles with PBKDF2-HMAC-SHA256 password protection.
* **Centralized Session Logging**: Live console streaming and ISO-timestamped session log file (`logs/session.log`) with ANSI color stripping.
* **System-wide Terminal Shortcut**: Instant execution anywhere via the **`ot`** terminal command.
* **Kernel TCP BBR Optimization**: Integrated Linux Kernel TCP BBR congestion control script (`vpn/tcp_bbr.sh`).
