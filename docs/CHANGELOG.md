# Changelog

## v2.5

* **Launcher bakes outbound server IPs at startup**: `vpn/singbox_proxification` resolves every domain `server` across outbounds via system DNS and writes the IP into the runtime config (`Resolved host -> ip` in logs) — the tunnel never resolves its own endpoint through itself, so the DoH-detour deadlock (`lookup ...: context deadline exceeded`) is gone for every protocol (vless/vmess/trojan/ss/hy2), both engines, TUN and proxy alike; TLS SNI / WS Host headers still carry the hostname so the handshake is unchanged, `socks-out`/`direct`/DoH untouched, unresolvable hosts left as-is with a warning, re-resolved on every (re)connect; audited all five v2ray parsers plus SSH modes and validated the full pipeline (import → socks rewrite → bake) against real `sing-box check`. The interim `local-dns`/`domain_resolver` workarounds are reverted (superseded, plus 1.14 rejects the route-field shape).
* **Trojan parser parity**: `allowInsecure`/`insecure` → `tls.insecure` and `alpn` (with the ws `h2`-strip) via the shared `_parse_insecure`/`_parse_alpn` helpers; `install-singbox-lx.sh` now exits when any `sing-box-lx` is already present; `build-deb.sh` bump `2.4` → `2.5`.
* **Mode-aware Edit menu**: `menu_edit` builds its rows from the active mode — `v2ray` shows Connection Mode, V2Ray Profile (remark + file, switches via the existing loader), Re-import Link, VPN Engine, Sing-Box Log, Open Raw Config, and hides the six SSH-only rows (server/auth/compression/proxy/payload/SNI); SSH modes unchanged.

## v2.4

* **sing-box-lx now the default engine**: `singbox-lx` (Leadaxe fork with XHTTP transport) joins `singbox`/`redsocks` as a third `engine_mode` and becomes the default everywhere (`ssh_parser.py` `DEFAULT_ENGINE`, `status_snapshot`, menus, `ssh.py`); new `install-singbox-lx.sh` one-liner installs it side-by-side as `sing-box-lx` (pinned `v1.14.1-lx.3`, `wget -c` resumable into `/tmp`, SHA-verified, sudo only for `/opt` install steps, never shadows stock); `find_engine_binary()` resolves per-engine (lx is PATH-only), 3-way engine picker replaces the toggle, `ssh://` links accept `engine=singbox-lx`; run path fails closed with switch/install hints (stock + xhttp profile, or lx selected but binary missing); README pushes stock down to an optional alternative-engine section.
* **VLESS parser gains xhttp / ALPN / allowInsecure**: `type=xhttp` maps to the fork's flat transport (`host`/`path`/`mode`, default `auto`) instead of being rejected, `alpn=h2,http/1.1` maps to `tls.alpn` — except on `ws`, where `h2` is stripped (CDNs negotiate HTTP/2 and the WS upgrade dies: every dial `EOF`, DNS garbage `unknown version: 72`) — and `allowInsecure=1` maps to `tls.insecure` (was silently dropped).
* **Proxy mode finally runs v2ray profiles**: `runvpn.sh` `connect()` execs `vpn/singbox_proxification` directly in `v2ray` mode (was misrouting through `ssh.py`, which only speaks SSH); the launcher no longer copies the saved profile verbatim — new `apply_output_mode()` rewrites `inbounds` per `OUTPUT_MODE` (`tun` vs socks+http on the instance's `OMNI_*` ports, outbounds/route/dns untouched), so already-saved TUN-only profiles work in proxy with no re-import and parallel instances stop colliding; `build-deb.sh` bump `2.3` → `2.4`.

## v2.3

* **Parallel proxy instances**: new `src/ports.py` central allocator (`find_free_port` / `allocate_proxy_ports` for SSH `-D 1080`, SOCKS-in `1081`, HTTP-in `8080`, injector `9008` via `OMNI_*` env) — every `runvpn.sh --proxy` run grabs its own free set (`+1` until free), `src/tunnel.py` binds `port+1` instead of exiting on conflict, `src/ssh.py` resolves `-D` `+1` until free and retries on `Could not request local forwarding`, `src/singbox_adapter.py` takes `socks_in_port`/`http_in_port` (env-aware, distinct, free-checked), `vpn/singbox_proxification` writes per-instance `cfgs/singbox_config_<socks_in>.json` (TUN keeps legacy path), and proxy cleanup is scoped to the instance (`killprocess_proxy` + port-pattern `pkill`, no global kill, TUN loop untouched); `build-deb.sh` bump `2.2` → `2.3`.
* **`ssh://` share links, unified with vless/trojan/ss/hy2**: new `src/ssh_parser.py` (`parse_ssh_uri` / `ssh_config_to_uri` / `parse_share_link` dispatcher) — `ssh://user[:pass]@host:port?auth&mode&sni&proxy&payload&key&compress&engine#Remark` maps straight onto `.ot` sections (`mode`/`ssh`/`Payload`/`sni`/`engine`), Import menu takes any scheme (ssh activates as current profile with optional library save) plus `Share current config as ssh:// link` with clipboard copy.
* **Per-instance profile snapshots (no more `active.ot` overlap)**: `runvpn.sh --proxy` copies the source `.ot` once to `/tmp/omnitunnel-active-<port>.ot` and exports `OMNI_PROFILE_PATH`, honored by `read_config()`/`effective_config_path()` across tunnel/ssh/sing-box — parallel proxies can run different profiles and menu edits never re-route live instances; `otunnel run <profile> --proxy` passes `OMNI_PROFILE_SRC` without touching `active.ot` (`.json`/TUN keep legacy paths); exit-only `cleanup_instance` removes the snapshot (per-reconnect kill leaves it); `export_profile_to_omni` writes atomically (tmp + `os.replace`) and corrupt `active.ot` now fails closed instead of being clobbered by the example template (seeding only on true first run).
* **Cleanup + unification**: delete uncalled `menu_edit_grouped`, `_pick_engine`/`_set_engine`, `menu_edit_payload`, `menu_edit_sni`, `_export_saved_library`, `LogServeMsg`, `pidkill.py`, unreachable `conf()` return, `tunnel.py` `__main__` dup; `git rm ConfMake` + drop `host1` pkill patterns (ssh cmd is built directly); shared `tun_inbound`/`direct_outbound`/`build_base_singbox` in `singbox_adapter.py` used by both it and `v2ray_parser.py` (outputs byte-identical); `cached_config`/`cached_snapshot` (mtime-invalidated, override-aware) replace ~24 per-render `active.ot` re-parses; single-place connect logging in `_ssh_attempt`; unused imports dropped.

## v2.2

* **CLI run commands**: `otunnel run [profile]` and `otunnel run --proxy [profile]` launch VPN/proxy directly from terminal without opening the menu; profile name is optional (partial match supported); shared `load_profile(name)` / `find_profile(name)` in `src/menu_common.py` eliminates duplication between CLI and menu load paths.

## v2.1

* **`otunnel run` CLI subcommands**: `otunnel run` starts the VPN (TUN engine) and `otunnel run --proxy` starts the proxy (SOCKS5 `1081` + HTTP `8080`) directly from the terminal, skipping the interactive menu — ideal for scripts, aliases, and headless launches; `menu.py` handles the `run`/`--proxy` argv before menu bootstrap (Ctrl+C cleanly stops both); `build-deb.sh` bump `2.0` → `2.1`.

## v2.0

* **Proxy Mode — SOCKS + HTTP instead of TUN**: new `2 Run Proxy` in the main menu (`1 Run / 2 Run Proxy / 3 Edit / 4 Load / 5 Import / 6 Profiles / 7 Logs / 8 Exit`) launches `runvpn.sh --proxy` and exposes **SOCKS5 on `0.0.0.0:1081`** + **HTTP on `0.0.0.0:8080`** for apps that only proxy (browsers, curl, Telegram), leaving the host network fully untouched — no TUN, no root-route changes, no interference with the SSH tunnel lifecycle; `src/singbox_adapter.py` `generate_singbox_config()` gains an `output_mode` param (`tun` default, `socks` → socks/http inbounds with the mixed stack dropped), `vpn/singbox_proxification` honors `OUTPUT_MODE` and prints the endpoint banner (`SOCKS5 → 0.0.0.0:1081` / `HTTP → 0.0.0.0:8080`), `runvpn.sh` parses `--proxy` (also `OUTPUT_MODE` env override) before engine resolution; `build-deb.sh` bump `1.4` → `2.0`.

## v1.4

* **Peak — connection workflow hardened**: `src/ssh.py` fixes malformed `publickey` `ssh -i` (was `ssh -i {password} publickey.pem useless@host`), now resolves key via `password` path → `cfgs/privatekey.pem` → `~/.ssh/id_*` with `IdentitiesOnly`, correct `user@host`, mode-aware `Direct SSH`/`TLS/SNI` banner, placeholder validation (abort on `your_username`/`vps.example.com` before `ssh -v`), `DNS: host→ip` log without replacing hostname, `load_hostkeys` flood suppressed, single-shot `singbox` engine (`_engine_launched` guard — was 6× `Launching singbox` per `Entering interactive session`), `sudo` once; `src/tunnel.py` fixes `CONNECT` parse (`regex` + `ssh_port` fallback), `v2ray` guard, `127.0.0.1:128` bind, **TLS insecure** `CERT_NONE`/`check_hostname=False` for SNI fronting (`example.com`→`178.170.25.195:8446` no longer `CERTIFICATE_VERIFY_FAILED`); `vpn/singbox_proxification` now reads unified `cfgs/saved/active.ot` via `read_config`/`status_snapshot` (was `cfgs/settings.ini`); `runvpn.sh` injector only for `1/2/3`, per-iteration mode re-read, `pkill sshpass.*ssh` fix; brand `omnitunnel-cli.svg` Kerr peak refresh.

## v1.3

* **Portal Import + mode-aware overview + alignment**: main menu now `1 Run / 2 Edit / 3 Load (silent+📂) / 4 Import (.ot portal → library same name → Load + Xray share link) / 5 Profiles (Save/Delete only) / 6 Logs / 7 Exit`; `Edit` adds `0 Open Raw Config` (`xdg-open active.ot`) and splits `SSH Auth Method`/`SSH Compression` into separate rows (`6 Auth` toggle, `7 Compression` toggle) moved before `VPN Engine`; `Current Configuration` aligned to `W=18` so all values start same column and is now mode-aware (`0` hides `Proxy/Payload/SNI`, `1` hides `SNI`, `2` hides `Proxy/Payload`, `3` shows all, `v2ray` shows `V2Ray Profile/Config`); `Sing-Box Log Level` → `Sing-Box Log` and ` — ● marks active` removed from titles (`Select Connection Mode`, `Sing-Box Log`).

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
