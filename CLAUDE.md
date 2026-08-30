# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development & Run Commands

### Run Commands
* **Launch Interactive CLI Menu**:
  ```bash
  sudo ./menu.py
  ```
  *(Launches the custom profile manager, proxy/payload/SNI configurations editor, and triggers the VPN connection)*

* **Launch Headless VPN directly**:
  ```bash
  sudo ./runvpn.sh
  ```
  *(Parses [cfgs/settings.ini](cfgs/settings.ini) configuration and initiates tunneling/proxification immediately)*

* **Import V2Ray / Xray Share Links (`vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://`)**:
  ```bash
  # Parse share URI and output sing-box 1.12+ config
  python3 src/v2ray_parser.py "vless://uuid@host:port?type=ws&security=tls#MyRemark"
  ```

* **Export / Import `.ot` Profiles**:
  ```bash
  # Export profile to .ot format
  python3 src/omni_profile.py export -i cfgs/settings.ini -o profile.ot -n "ProfileName" --password "secret"

  # Import .ot format to settings.ini
  python3 src/omni_profile.py import -i profile.ot -o cfgs/settings.ini --password "secret"
  ```

### Build/Compiling Commands
Build dependencies are managed automatically on launch by [runvpn.sh](runvpn.sh). It compiles missing binaries from [libs/](libs/) on the fly:
* **Compile Redsocks**: Done automatically from [libs/redsocks.zip](libs/redsocks.zip) to [bin/redsocks](bin/redsocks)
* **Compile Dns2socks**: Done automatically from [libs/dns2socks.zip](libs/dns2socks.zip) to [bin/dns2socks](bin/dns2socks)

## Architecture Overview

OmniTunnel CLI is a Python & Shell-based VPN client utilizing custom HTTP payloads, SSL SNI spoofing, and SSH-encrypted tunnels to bypass network firewalls. It operates by modifying the system's low-level routing tables via iptables.

### Data & Execution Flow
1. **Interactive UI / Config**: [menu.py](menu.py) manages system-wide configurations and profiles stored under [cfgs/](cfgs/). Active settings are stored in [cfgs/settings.ini](cfgs/settings.ini).
2. **Startup Script**: [runvpn.sh](runvpn.sh) verifies that local dependencies exist, binds traps for clean signal handling (SIGINT/SIGTERM), kills old routing or background tunnel processes, and cycles local TCP ports to launch [main.py](main.py) and [src/ssh.py](src/ssh.py).
3. **Payload Injection & SNI Proxy Server**: [main.py](main.py) initiates the connection handler in [src/tunnel.py](src/tunnel.py).
   * It spins up a local TCP listener on a dynamic port.
   * If SNI spoofing (Modes 2/3) is enabled, it wraps the connection inside an SSL context utilizing Python's `ssl` library and spoofed SNI hostnames.
   * It uses [src/inject.py](src/inject.py) to format custom injection payloads, substituting wildcard placeholders (`[crlf]`, `[host]`, `[port]`, etc.) to generate mock HTTP headers.
4. **SSH Tunneling**: Once the injection handshake succeeds, [src/ssh.py](src/ssh.py) sets up a dynamic socks5 port forward over SSH using `ssh` or `sshpass`. It uses [ConfMake](ConfMake) to generate a compatible `configFile` configuration defining supported SSH key types and host key algorithms for modern Linux systems.
5. **System Proxification & Routing**: Once SSH is established, `src/ssh.py` executes [vpn/proxification](vpn/proxification).
   * This shell script establishes custom `iptables` rules, redirecting outbound TCP traffic to `redsocks`.
   * It executes [bin/redsocks](bin/redsocks) in a background screen, mapping iptables redirections to the SOCKS5 dynamic forward port.
   * It starts [bin/dns2socks](bin/dns2socks) to tunnel DNS lookups (UDP/TCP port 53 traffic) cleanly over the SOCKS5 proxy to public resolver servers (e.g. `8.8.8.8`).
6. **Graceful Shutdown**: Interruption triggers the termination loop via [src/pidkill.py](src/pidkill.py) or `runvpn.sh` traps, removing `iptables` rules and restoring system DNS settings (`resolv.conf`).
7. **Centralized Logging System**: All console logs, SSH events, tunnel handshakes, and `sing-box` engine logs are processed through [src/logger.py](src/logger.py). Entries are timestamped, stripped of ANSI color codes for file logging, and recorded in `logs/session.log` while streaming to standard terminal console in real-time.
