#!/bin/bash

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
SCOLOR='\033[0m'

# Get the absolute path of the project root
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure local bin directory exists
mkdir -p "$PROJECT_DIR/bin"

# Add local bin to PATH and ensure Python imports work regardless of cwd
export PATH="$PROJECT_DIR/bin:$PATH"
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"

# Output mode: --proxy exposes SOCKS+HTTP ports instead of TUN
export OUTPUT_MODE="${OUTPUT_MODE:-tun}"
for arg in "$@"; do
    if [ "$arg" = "--proxy" ]; then
        export OUTPUT_MODE=socks
    fi
done

# Engine mode (singbox = default, no compile needed) — unified active.ot
engine=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from src.menu_common import read_config, status_snapshot; print(status_snapshot(read_config())['engine_mode'])" 2>/dev/null || echo singbox)

if [ "$engine" != "redsocks" ]; then
    echo -e "${GREEN}Engine: Sing-Box (no compilation required)${SCOLOR}"
else

# Compile and check redsocks (legacy engine only)
if command -v redsocks >/dev/null; then
    echo -e "${GREEN}Redsocks is available${SCOLOR}"
else
    echo -e "${YELLOW}Redsocks not found. Compiling...${SCOLOR}"
    if [ -f "$PROJECT_DIR/libs/redsocks.zip" ]; then
        rm -rf "$PROJECT_DIR/redsocks"
        unzip -qo "$PROJECT_DIR/libs/redsocks.zip" -d "$PROJECT_DIR"
        cd "$PROJECT_DIR/redsocks" || exit 1
        make || exit 1
        cp redsocks "$PROJECT_DIR/bin/"
        if [ -n "$PREFIX" ] && [ -d "$PREFIX/bin" ] && [ -w "$PREFIX/bin" ]; then
            cp redsocks "$PREFIX"/bin/ 2>/dev/null
        fi
        cd "$PROJECT_DIR"
        rm -rf "$PROJECT_DIR/redsocks"
        echo -e "${GREEN}Redsocks compiled successfully!${SCOLOR}"
    else
        echo -e "${RED}Error: libs/redsocks.zip not found.${SCOLOR}"
        exit 1
    fi
fi

# Compile and check dns2socks (legacy engine only)
if command -v dns2socks >/dev/null; then
    echo -e "${GREEN}Dns2socks is available${SCOLOR}"
else
    echo -e "${YELLOW}Dns2socks not found. Compiling...${SCOLOR}"
    if [ -f "$PROJECT_DIR/libs/dns2socks.zip" ]; then
        rm -rf "$PROJECT_DIR/dns2socks"
        unzip -qo "$PROJECT_DIR/libs/dns2socks.zip" -d "$PROJECT_DIR"
        cd "$PROJECT_DIR/dns2socks" || exit 1
        make || exit 1
        cp dns2socks "$PROJECT_DIR/bin/"
        if [ -n "$PREFIX" ] && [ -d "$PREFIX/bin" ] && [ -w "$PREFIX/bin" ]; then
            cp dns2socks "$PREFIX"/bin/ 2>/dev/null
        fi
        cd "$PROJECT_DIR"
        rm -rf "$PROJECT_DIR/dns2socks"
        echo -e "${GREEN}Dns2socks compiled successfully!${SCOLOR}"
    else
        echo -e "${RED}Error: libs/dns2socks.zip not found.${SCOLOR}"
        exit 1
    fi
fi

fi

clear
python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from src.logger import log_session_start; log_session_start()" 2>/dev/null

mode=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from src.menu_common import read_config, status_snapshot; print(status_snapshot(read_config())['mode'])" 2>/dev/null || echo 1)

killprocess() {
echo -e "${RED}[+] KILLING PROCESS...."
pkill -f "python3.*src/ssh.py" 2>/dev/null || true
# kill ssh via injector (mode 1/2/3) and direct ssh (mode 0)
pkill -f "ssh.*-CND 1080" 2>/dev/null || true
pkill -f "sshpass.*ssh" 2>/dev/null || true
pkill redsocks 2>/dev/null || true
pkill dns2socks 2>/dev/null || true
pkill sing-box 2>/dev/null || true
# vaydns backends (all of them — TUN is single-instance)
pkill -f "vaydns-client.*-listen" 2>/dev/null || true
python3 "$PROJECT_DIR/src/vaydns.py" down 2>/dev/null || true
pkill -f "python3.*main.py" 2>/dev/null || true
echo -e "[+] DONE ${SCOLOR}"
}

# Scoped cleanup for proxy mode: only this instance's ports, so parallel
# proxies (multiple `runvpn.sh --proxy`) don't kill each other.
killprocess_proxy() {
echo -e "${RED}[+] KILLING PROXY INSTANCE (ssh -D ${OMNI_SSH_SOCKS_PORT:-1080}, socks ${OMNI_SOCKS_IN_PORT:-1081}, http ${OMNI_HTTP_IN_PORT:-8080}, injector ${OMNI_INJECTOR_PORT:-9008})...."
if [ -n "${INJECTOR_PID:-}" ]; then
    kill "$INJECTOR_PID" 2>/dev/null || true
fi
if [ -n "${OMNI_SSH_SOCKS_PORT:-}" ]; then
    pkill -f "ssh.*-CND ${OMNI_SSH_SOCKS_PORT}" 2>/dev/null || true
fi
if [ -n "${OMNI_INJECTOR_PORT:-}" ]; then
    pkill -f "main.py ${OMNI_INJECTOR_PORT}" 2>/dev/null || true
fi
if [ -n "${OMNI_SOCKS_IN_PORT:-}" ]; then
    pkill -f "sing-box.*singbox_config_${OMNI_SOCKS_IN_PORT}.json" 2>/dev/null || true
fi
# vaydns backends owned by this instance only (parallel-safe)
if [ -n "${OMNI_VAYDNS_PORTS:-}" ]; then
    python3 "$PROJECT_DIR/src/vaydns.py" down --ports "$OMNI_VAYDNS_PORTS" 2>/dev/null || true
fi
if [ -n "${OMNI_VAYDNS_SOCKS:-}" ]; then
    python3 "$PROJECT_DIR/src/vaydns.py" down --socks "$OMNI_VAYDNS_SOCKS" 2>/dev/null || true
fi
# ...or via this instance's ports files (launcher-owned lifecycle)
if [ -n "${OMNI_SOCKS_IN_PORT:-}" ]; then
    if [ -f "/tmp/omnitunnel-vaydns-${OMNI_SOCKS_IN_PORT}.socks" ]; then
        python3 "$PROJECT_DIR/src/vaydns.py" down --socks "$(cat "/tmp/omnitunnel-vaydns-${OMNI_SOCKS_IN_PORT}.socks")" 2>/dev/null || true
    fi
    if [ -f "/tmp/omnitunnel-vaydns-${OMNI_SOCKS_IN_PORT}.ports" ]; then
        python3 "$PROJECT_DIR/src/vaydns.py" down --ports "$(cat "/tmp/omnitunnel-vaydns-${OMNI_SOCKS_IN_PORT}.ports")" 2>/dev/null || true
    fi
fi
pkill -P $$ 2>/dev/null || true
echo -e "[+] DONE ${SCOLOR}"
}

# Exit-only cleanup for proxy mode: process kill + remove this instance's
# profile snapshot (killprocess_proxy alone runs after every reconnect and
# must NOT delete the snapshot mid-loop).
cleanup_instance() {
killprocess_proxy 2>/dev/null || true
if [ "${OMNI_PROFILE_OWNED:-}" = "1" ] && [ -n "${OMNI_PROFILE_PATH:-}" ]; then
    rm -f "$OMNI_PROFILE_PATH" 2>/dev/null || true
fi
}

# Intercept Ctrl+C (SIGINT) and SIGTERM to stop everything immediately
# Proxy mode uses scoped cleanup (parallel instances safe); TUN keeps global.
# Instance snapshot removal happens only on exit, never between reconnects.
if [ "$OUTPUT_MODE" = "socks" ]; then
    trap 'cleanup_instance; exit 1' INT TERM
    trap 'cleanup_instance' EXIT
else
    trap 'killprocess; exit 1' INT TERM
    trap 'killprocess' EXIT
fi

function serverlistening() {
    localport="$1"
    # Only start injector when needed (modes 1/2/3); v2ray, vaydns and direct 0 skip
    if [ "$mode" = "v2ray" ] || [ "$mode" = "vaydns" ] || [ "$mode" = "0" ]; then
        return 0
    fi
    OMNI_INJECTOR_PORT="$localport" python3 "$PROJECT_DIR/main.py" $localport &
    INJECTOR_PID=$!
    echo ""
}
function connect() {
        localport="$1"
        # re-read mode per iteration (instance snapshot in proxy mode,
        # global active.ot in TUN mode)
        cur_mode=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from src.menu_common import read_config, status_snapshot; print(status_snapshot(read_config())['mode'])" 2>/dev/null || echo "$mode")
        # v2ray/vaydns have no SSH leg: hand straight to the sing-box
        # launcher (same as the TUN path) instead of ssh.py, which only
        # speaks SSH. The launcher owns vaydns-client backends end to end.
        if [ "$cur_mode" = "v2ray" ] || [ "$cur_mode" = "vaydns" ]; then
            exec sudo -E bash "$PROJECT_DIR/vpn/singbox_proxification"
        fi
	if [ "$cur_mode" = "0" ]
        then
           python3 "$PROJECT_DIR/src/ssh.py" 0
    else
           python3 "$PROJECT_DIR/src/ssh.py" $localport
	fi
}

if [ "$mode" = "v2ray" ] || [ "$mode" = "vaydns" ]; then
    echo -e "${GREEN}[+] Launching Sing-Box Engine with ${mode} Profile...${SCOLOR}"
    exec sudo -E bash "$PROJECT_DIR/vpn/singbox_proxification"
    exit 0
fi

if [ "$OUTPUT_MODE" = "socks" ]; then
    # Proxy mode: allocate 4 distinct free ports once per instance (+1 until free).
    # Parallel `runvpn.sh --proxy` runs each get their own set — no collisions.
    eval "$(python3 -c "
import sys; sys.path.insert(0, '$PROJECT_DIR')
from src.ports import allocate_proxy_ports
p = allocate_proxy_ports()
print('export OMNI_SSH_SOCKS_PORT=%s OMNI_SOCKS_IN_PORT=%s OMNI_HTTP_IN_PORT=%s OMNI_INJECTOR_PORT=%s' % (p['ssh_socks'], p['socks_in'], p['http_in'], p['injector']))
" 2>/dev/null)" || {
        export OMNI_SSH_SOCKS_PORT="${OMNI_SSH_SOCKS_PORT:-1080}"
        export OMNI_SOCKS_IN_PORT="${OMNI_SOCKS_IN_PORT:-1081}"
        export OMNI_HTTP_IN_PORT="${OMNI_HTTP_IN_PORT:-8080}"
        export OMNI_INJECTOR_PORT="${OMNI_INJECTOR_PORT:-9008}"
    }
    export OMNI_SSH_SOCKS_PORT OMNI_SOCKS_IN_PORT OMNI_HTTP_IN_PORT OMNI_INJECTOR_PORT
    echo -e "${GREEN}[+] Proxy instance ports: SSH -D ${OMNI_SSH_SOCKS_PORT}, SOCKS ${OMNI_SOCKS_IN_PORT}, HTTP ${OMNI_HTTP_IN_PORT}, injector ${OMNI_INJECTOR_PORT}${SCOLOR}"
    # Instance profile snapshot: cp the source .ot once, point the whole
    # instance at the copy via OMNI_PROFILE_PATH. Later menu edits / loads
    # can never re-route or corrupt this running instance, and two parallel
    # proxies can use two different profiles. Source is OMNI_PROFILE_SRC
    # (otunnel run <profile> --proxy) or the global active.ot otherwise.
    PROFILE_SRC="${OMNI_PROFILE_SRC:-$PROJECT_DIR/cfgs/saved/active.ot}"
    export OMNI_PROFILE_PATH="/tmp/omnitunnel-active-${OMNI_SOCKS_IN_PORT}.ot"
    export OMNI_PROFILE_OWNED=1
    if ! cp "$PROFILE_SRC" "$OMNI_PROFILE_PATH" 2>/dev/null; then
        echo -e "${RED}Error: cannot snapshot profile '$PROFILE_SRC' — aborting instance.${SCOLOR}"
        exit 1
    fi
    echo -e "${GREEN}[+] Proxy instance profile: ${PROFILE_SRC} → ${OMNI_PROFILE_PATH}${SCOLOR}"
    # No global kill here — that would take down other proxy instances.
    for i in {1..9999}
    do
        echo -e "$GREEN ++++ LOGS ++++$SCOLOR"
        rm -f "$PROJECT_DIR/logs.txt" 2>/dev/null || true
        serverlistening "$OMNI_INJECTOR_PORT"
        sleep 1
        connect "$OMNI_INJECTOR_PORT"
        killprocess_proxy
        sleep 1
    done
    exit 0
fi

# Clean any stale tunnel from previous run before binding (TUN single-instance)
killprocess 2>/dev/null || true
sleep 1

for i in {9008..9999}
do
    echo -e "$GREEN ++++ LOGS ++++$SCOLOR"
	rm -f "$PROJECT_DIR/logs.txt" 2>/dev/null || true
	serverlistening $i
	sleep 1
	connect $i
    killprocess
    sleep 1
done

