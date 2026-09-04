#!/usr/bin/env bash
# ==============================================================================
# OmniTunnel CLI - Uninstaller
# Repository: https://github.com/RadouaneElarfaoui/omnitunnel-cli
# ==============================================================================

set -e

C_RESET='\033[0m'
C_RED='\033[1;31m'
C_GREEN='\033[1;32m'
C_YELLOW='\033[1;33m'
C_BLUE='\033[1;34m'
C_CYAN='\033[1;36m'
C_BOLD='\033[1m'

INSTALL_DIR="/opt/omnitunnel-cli"
BIN_LINK="/usr/local/bin/otunnel"

echo -e "${C_CYAN}${C_BOLD}"
echo "  ___                  _ _____                  _ "
echo " / _ \ _ __ ___  _ __ (_)__   |_   _ _ __  _ __   ___| |"
echo "| | | | '_ \` _ \| '_ \| | / /\ | | | | '_ \| '_ \ / _ \ |"
echo "| |_| | | | | | | | | | |/ /  | |_| | | | | | | |  __/ |"
echo " \___/|_| |_| |_|_| |_|_/_/    \__,_|_| |_|_| |_|\___|_|"
echo -e "       OmniTunnel CLI Uninstaller${C_RESET}\n"
printf '%b' "${C_CYAN}${C_BOLD}"
cat << 'EOF'
  ___   __  __  _   _  ___  _____  _   _  _   _  _   _  _____  _     
 / _ \ |  \/  || \ | ||_ _||_   _|| | | || \ | || \ | || ____|| |    
| | | || |\/| ||  \| | | |   | |  | | | ||  \| ||  \| ||  _|  | |    
| |_| || |  | || |\  | | |   | |  | |_| || |\  || |\  || |___ | |___ 
 \___/ |_|  |_||_| \_||___|  |_|   \___/ |_| \_||_| \_||_____||_____|
EOF
printf '%b\n' "${C_RESET}"
echo -e "       OmniTunnel CLI Uninstaller\n"

# ------------------------------------------------------------------------------
# 1. Root Privileges Check
# ------------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo -e "${C_RED}[✕] Error: This script must be run as root.${C_RESET}"
    echo -e "Please run: ${C_YELLOW}curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/uninstall.sh | sudo bash${C_RESET}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Terminate Active OmniTunnel VPN Processes
# ------------------------------------------------------------------------------
echo -e "${C_BLUE}[*] Terminating any running OmniTunnel processes...${C_RESET}"
pkill -f "python3.*omnitunnel.*/menu.py" 2>/dev/null || true
pkill -f "python3.*src/ssh.py" 2>/dev/null || true
pkill -f "ssh.*-CND 1080" 2>/dev/null || true
pkill -f "sshpass.*host1" 2>/dev/null || true
pkill -f "python3.*main.py.*900" 2>/dev/null || true
pkill redsocks 2>/dev/null || true
pkill dns2socks 2>/dev/null || true
pkill sing-box 2>/dev/null || true
echo -e "${C_GREEN}[✔] Background processes stopped.${C_RESET}"

# ------------------------------------------------------------------------------
# 3. Remove Binary Launcher Link
# ------------------------------------------------------------------------------
echo -e "\n${C_BLUE}[*] Removing terminal command ($BIN_LINK)...${C_RESET}"
if [ -f "$BIN_LINK" ] || [ -L "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    echo -e "${C_GREEN}[✔] Removed $BIN_LINK${C_RESET}"
else
    echo -e "    $BIN_LINK was not found."
fi

# Clean up legacy names if present
rm -f /usr/local/bin/ot /usr/local/bin/omnitunnel 2>/dev/null || true

# ------------------------------------------------------------------------------
# 4. Remove Project Directory /opt/omnitunnel-cli
# ------------------------------------------------------------------------------
if [ -d "$INSTALL_DIR" ]; then
    echo -e "\n${C_BLUE}[*] Removing installation directory: $INSTALL_DIR...${C_RESET}"
    
    # Check if there are user profiles in saved configs
    SAVED_PROFILES=$(find "$INSTALL_DIR/cfgs/saved" -type f -name "*.ot" 2>/dev/null | wc -l || echo "0")
    if [ "$SAVED_PROFILES" -gt 0 ] && [ -t 0 ] && [ "$1" != "--purge" ] && [ "$1" != "-y" ]; then
        BACKUP_DIR="${SUDO_USER:+/home/$SUDO_USER}/.omnitunnel_backup"
        if [ -n "$SUDO_USER" ] && [ -d "/home/$SUDO_USER" ]; then
            echo -e "${C_YELLOW}[!] Found $SAVED_PROFILES saved profile(s). Backing up to $BACKUP_DIR...${C_RESET}"
            mkdir -p "$BACKUP_DIR"
            cp -r "$INSTALL_DIR/cfgs/saved" "$BACKUP_DIR/" 2>/dev/null || true
            if [ -f "$INSTALL_DIR/cfgs/settings.ini" ]; then
                cp "$INSTALL_DIR/cfgs/settings.ini" "$BACKUP_DIR/" 2>/dev/null || true
            fi
            chown -R "$SUDO_USER:$SUDO_USER" "$BACKUP_DIR" 2>/dev/null || true
            echo -e "${C_GREEN}[✔] Configurations backed up to $BACKUP_DIR${C_RESET}"
        fi
    fi

    rm -rf "$INSTALL_DIR"
    echo -e "${C_GREEN}[✔] Removed $INSTALL_DIR${C_RESET}"
else
    echo -e "    $INSTALL_DIR not found."
fi

# ------------------------------------------------------------------------------
# 5. Complete
# ------------------------------------------------------------------------------
echo -e "\n${C_GREEN}${C_BOLD}======================================================${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}  OmniTunnel CLI has been uninstalled successfully.   ${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}======================================================${C_RESET}\n"

