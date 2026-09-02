# Changelog

## v1.1.0

* **V2Ray / Xray / Sing-Box Protocols Support**: Parse and import share links (`vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://` / `hysteria2://`) with REALITY, uTLS, WebSocket, and gRPC.
* **Next-Gen Sing-Box TUN Engine**: High-performance **`sing-box`** TUN interface (`tun0`) with DoH (DNS-over-HTTPS) caching and 3x–5x higher throughput.
* **Encrypted `.ot` Profile Format**: Export and import `.ot` (OmniTunnel) custom profiles with PBKDF2-HMAC-SHA256 password protection.
* **Centralized Session Logging**: Live console streaming and ISO-timestamped session log file (`logs/session.log`) with ANSI color stripping.
* **System-wide Terminal Shortcut**: Instant execution anywhere via the **`ot`** terminal command.
* **Kernel TCP BBR Optimization**: Integrated Linux Kernel TCP BBR congestion control script (`vpn/tcp_bbr.sh`).
