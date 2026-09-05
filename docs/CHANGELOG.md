# Changelog

## v1.2

* **Unified config + main-menu Load**: single active store `cfgs/saved/active.ot` (JSON `.ot` via `import_profile_from_omni`/`export_profile_to_omni` + `status_snapshot`/`read_config`/`write_config`); single `.ot` library (`.ini` dropped); `src/ssh.py` builds `ssh` cmd directly (drop `ConfMake`/`cfgs/configFile` shim + `auth_methode` fallback); `runvpn.sh`/`install.sh`/`uninstall.sh`/`v2ray_parser` read via `status_snapshot`; `SAVED_CONFIGS_DIR` is the only `777` dir (remove `cfgs` 777 fork) in `ensure_saved_configs_dir`/`install.sh`/`build-deb.sh` (`build-deb.sh` postinst + payload fixed); `cfgs/settings.ot.example` is the only fallback renderer; `build-deb.sh` still slim. **Menu**: main menu now `1 Run / 2 Edit / 3 Load (silent)` — `Load` is the same library picker as `Profiles → Load` but silent (no `loaded successfully`/`Press Enter`) and starts with `📂 Open Folder` (`xdg-open cfgs/saved`, loops back); both pickers now share the open-folder header (`xdg-open` via `Popen` `start_new_session`).

## v1.1.7

* **Menu rework — no duplication, inline editing, toggles**: `Edit` now shows the same `Current Configuration` lines as the main overview but selectable (↑↓ cycles the preview lines); `VPN Engine`/`Log Level` moved to bottom (rarely changed); `Proxy Server` edits inline (`ip:port` prefilled) instead of submenu; `Password`/`auth` remain inline with `readline` prefill for in-place edit (fix `Edit Proxy [ip:port]: …` duplication); `Auth Method`/`Compression`/`Engine` collapsed from 2-option submenus to direct toggles; `Export Profile` collapsed from 2-option submenu to single pick-list (`▶ Current` + library); removed redundant `Connection mode updated / Press Enter` confirms for trivial selects; `menu_common` centralizes `status_snapshot`/`input_editable`/`stay_after`/`break_after` and fixes arrow-menu highlight memory (`←/Esc` → Back); `build-deb.sh` already slim.

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
