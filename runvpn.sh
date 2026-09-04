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

# Engine mode (singbox = default, no compile needed)
engine=$(grep "engine_mode" "$PROJECT_DIR/cfgs/settings.ini" | awk '{print $3}' | tr -d '\r')

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

mode=$(cat "$PROJECT_DIR/cfgs/settings.ini" |grep "connection_mode"| awk '{print $3}')

killprocess() {
echo -e "${RED}[+] KILLING PROCESS...."
pkill -f "python3.*src/ssh.py" 2>/dev/null || true
# only kill the tunnel's ssh clients (dynamic forward -CND 1080 / host1), never sshd/ssh-agent
pkill -f "ssh.*-CND 1080" 2>/dev/null || true
pkill -f "sshpass.*host1" 2>/dev/null || true
pkill redsocks 2>/dev/null || true
pkill dns2socks 2>/dev/null || true
pkill sing-box 2>/dev/null || true
pkill -f "python3.*main.py" 2>/dev/null || true
echo -e "[+] DONE ${SCOLOR}"
}

# Intercept Ctrl+C (SIGINT) and SIGTERM to stop everything immediately
trap 'killprocess; exit 1' INT TERM
trap 'killprocess' EXIT

function serverlistening() {
    localport="$1"
    python3 "$PROJECT_DIR/main.py" $localport &
    echo ""
}
function connect() {
        localport="$1"

	if [ "$mode" = "0" ]
        then
           python3 "$PROJECT_DIR/src/ssh.py" 0
    else

			python3 "$PROJECT_DIR/src/ssh.py" $localport

	fi

}

if [ "$mode" = "v2ray" ]; then
    echo -e "${GREEN}[+] Launching Sing-Box TUN Engine with V2Ray/Xray Profile...${SCOLOR}"
    exec sudo -E bash "$PROJECT_DIR/vpn/singbox_proxification"
    exit 0
fi

for i in {9008..9999}
do

    echo -e "$GREEN ++++ LOGS ++++$SCOLOR"
	rm -f "$PROJECT_DIR/logs.txt" 2>/dev/null || true
	serverlistening $i
	sleep 1
	connect $i
    killprocess
done


