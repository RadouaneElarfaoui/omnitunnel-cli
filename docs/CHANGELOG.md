# Changelog

## v1.1.6

* **Slim deb**: `build-deb.sh` now excludes `docs/` (images ~200K) and `libs/` (`redsocks.zip` 1.39M + `dns2socks.zip` 80K); deb drops from ~1.5M to ~100K. `install.sh`/`runvpn.sh` still fetch/compile `libs/` on demand if needed.

## v1.1.5

* **Saved profiles permission fix**: `cfgs/saved` is now `777` in the `.deb` payload and `postinst`/`install.sh`, and `ensure_saved_configs_dir()` ensures `777`, so non-sudo `otunnel` can save `.ot` profiles without `Permission denied`.

## v1.1.4

* **No-sudo configFile fix**: `ConfMake` now writes to `cfgs/configFile` (777) instead of the root install dir (755), and `src/ssh.py` reads from there, so the non-sudo menu (`otunnel`) no longer fails with `Permission denied` on `configFile` creation.

## v1.1.3

* **No-sudo launcher**: `otunnel` wrapper no longer prefixes `sudo`; the menu opens without a password prompt and only `Run VPN` / `BBR` / `sing-box` elevate via `sudo` internally, matching the desktop `Terminal=true` flow.

## v1.1.2

* **Tunnel reuse fix**: `src/tunnel.py` now sets `SO_REUSEADDR` before `bind()` and exits cleanly with a logged error instead of falling through to `accept()` with `None` (`Coudn't open socket` / `NoneType accept`). `runvpn.sh` now kills any stale `main.py` before the first bind and sleeps after each `killprocess` so the port is released before the next iteration or next `Run VPN` click.

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
