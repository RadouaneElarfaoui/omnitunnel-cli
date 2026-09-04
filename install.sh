#!/usr/bin/env bash
# ==============================================================================
# OmniTunnel CLI - One-Line Installer
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
REPO_URL="https://github.com/RadouaneElarfaoui/omnitunnel-cli.git"
SINGBOX_VERSION="1.14.0"

printf '%b' "${C_CYAN}${C_BOLD}"
cat << 'EOF'
  ___   __  __  _   _  ___  _____  _   _  _   _  _   _  _____  _     
 / _ \ |  \/  || \ | ||_ _||_   _|| | | || \ | || \ | || ____|| |    
| | | || |\/| ||  \| | | |   | |  | | | ||  \| ||  \| ||  _|  | |    
| |_| || |  | || |\  | | |   | |  | |_| || |\  || |\  || |___ | |___ 
 \___/ |_|  |_||_| \_||___|  |_|   \___/ |_| \_||_| \_||_____||_____|
EOF
printf '%b\n' "${C_RESET}"
echo -e "       OmniTunnel CLI Installer (One-Line Setup)\n"

# ------------------------------------------------------------------------------
# 1. Root Privileges Check
# ------------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo -e "${C_RED}[✕] Error: This script must be run as root.${C_RESET}"
    echo -e "Please run: ${C_YELLOW}curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/install.sh | sudo bash${C_RESET}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Operating System Check
# ------------------------------------------------------------------------------
if ! command -v apt-get >/dev/null 2>&1; then
    echo -e "${C_RED}[✕] Error: apt-get package manager not found.${C_RESET}"
    echo -e "This installer currently supports Debian/Ubuntu-based distributions."
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. Check and Install Missing APT Dependencies (Strict Essentials Only)
# ------------------------------------------------------------------------------
echo -e "${C_BLUE}[*] Checking required system dependencies...${C_RESET}"

# Strictly required runtime dependencies:
# - openssh-client : SSH client
# - sshpass        : non-interactive password authentication
# - netcat-openbsd : tunnel proxy command (nc)
# - python3        : runtime environment
# - python3-certifi: SSL certificates
# - iptables       : network routing & transparent proxy rules
REQUIRED_PACKAGES=(
    openssh-client
    sshpass
    netcat-openbsd
    python3
    python3-certifi
    iptables
)

# Ensure at least one HTTP downloader (curl or wget) is present
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    REQUIRED_PACKAGES+=(curl)
fi

MISSING_PACKAGES=()
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        echo -e "    ${C_GREEN}✔${C_RESET} $pkg ${C_CYAN}(already installed)${C_RESET}"
    else
        echo -e "    ${C_YELLOW}⚠${C_RESET} $pkg ${C_YELLOW}(missing, will be installed)${C_RESET}"
        MISSING_PACKAGES+=("$pkg")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "\n${C_BLUE}[*] Updating package indices and installing missing packages: ${MISSING_PACKAGES[*]}...${C_RESET}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends "${MISSING_PACKAGES[@]}"
    echo -e "${C_GREEN}[✔] All required system packages are now installed.${C_RESET}"
else
    echo -e "${C_GREEN}[✔] All required system packages are already present. No apt download needed.${C_RESET}"
fi

# ------------------------------------------------------------------------------
# 4. Check and Install Sing-Box Engine (Skip if already present)
# ------------------------------------------------------------------------------
echo -e "\n${C_BLUE}[*] Checking Sing-Box TUN engine...${C_RESET}"

SINGBOX_PATH=""
if command -v sing-box >/dev/null 2>&1; then
    SINGBOX_PATH="$(command -v sing-box)"
elif [ -x "/usr/bin/sing-box" ]; then
    SINGBOX_PATH="/usr/bin/sing-box"
elif [ -x "/usr/local/bin/sing-box" ]; then
    SINGBOX_PATH="/usr/local/bin/sing-box"
fi

if [ -n "$SINGBOX_PATH" ]; then
    SB_VER="$("$SINGBOX_PATH" version 2>/dev/null | head -n 1 || echo "installed")"
    echo -e "${C_GREEN}[✔] Sing-Box is already installed at $SINGBOX_PATH ($SB_VER). Skipping download.${C_RESET}"
else
    echo -e "${C_YELLOW}[!] Sing-Box not found. Determining hardware architecture...${C_RESET}"
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64)
            SINGBOX_ARCH="amd64"
            ;;
        aarch64|arm64)
            SINGBOX_ARCH="arm64"
            ;;
        armv7l|armhf)
            SINGBOX_ARCH="armv7"
            ;;
        i386|i686)
            SINGBOX_ARCH="386"
            ;;
        *)
            echo -e "${C_RED}[✕] Unsupported architecture for Sing-Box .deb: $ARCH${C_RESET}"
            echo -e "You can manually install sing-box from: https://github.com/SagerNet/sing-box/releases"
            exit 1
            ;;
    esac

    DEB_URL="https://github.com/SagerNet/sing-box/releases/download/v${SINGBOX_VERSION}/sing-box_${SINGBOX_VERSION}_linux_${SINGBOX_ARCH}.deb"
    DEB_TMP="/tmp/sing-box_${SINGBOX_VERSION}_linux_${SINGBOX_ARCH}.deb"

    echo -e "${C_BLUE}[*] Downloading Sing-Box v${SINGBOX_VERSION} (${SINGBOX_ARCH})...${C_RESET}"
    wget -q --show-progress -O "$DEB_TMP" "$DEB_URL" || curl -fsSL "$DEB_URL" -o "$DEB_TMP"

    echo -e "${C_BLUE}[*] Installing Sing-Box package...${C_RESET}"
    dpkg -i "$DEB_TMP" || apt-get install -f -y
    rm -f "$DEB_TMP"

    echo -e "${C_GREEN}[✔] Sing-Box installed successfully.${C_RESET}"
fi

# ------------------------------------------------------------------------------
# 5. Deploy Project Files to /opt/omnitunnel-cli
# ------------------------------------------------------------------------------
echo -e "\n${C_BLUE}[*] Setting up OmniTunnel CLI in $INSTALL_DIR...${C_RESET}"

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"

if [ -f "$CURRENT_DIR/menu.py" ] && [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
    # Local execution from an existing git clone
    echo -e "    Copying files from current source directory: $CURRENT_DIR"
    mkdir -p "$INSTALL_DIR"
    cp -r "$CURRENT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$CURRENT_DIR"/.[!.]* "$INSTALL_DIR/" 2>/dev/null || true
    rm -rf "$INSTALL_DIR/.venv" "$INSTALL_DIR/__pycache__" "$INSTALL_DIR/src/__pycache__"
elif [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "    OmniTunnel CLI repository already exists in $INSTALL_DIR. Updating..."
    cd "$INSTALL_DIR"
    git pull || echo -e "${C_YELLOW}[!] Could not update git repository; keeping current files.${C_RESET}"
elif [ ! -d "$INSTALL_DIR" ]; then
    if command -v git >/dev/null 2>&1; then
        echo -e "    Cloning repository via git..."
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    else
        echo -e "    Downloading repository archive (git-free)..."
        mkdir -p "$INSTALL_DIR"
        TAR_URL="https://github.com/RadouaneElarfaoui/omnitunnel-cli/archive/refs/heads/main.tar.gz"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "$TAR_URL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        elif command -v wget >/dev/null 2>&1; then
            wget -qO- "$TAR_URL" | tar -xz --strip-components=1 -C "$INSTALL_DIR"
        fi
    fi
fi

# Ensure default directories and configuration
mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/logs" "$INSTALL_DIR/cfgs/saved"

if [ ! -f "$INSTALL_DIR/cfgs/settings.ini" ] && [ -f "$INSTALL_DIR/cfgs/settings.ot.example" ]; then
    echo -e "    Creating default settings.ini..."
    cp "$INSTALL_DIR/cfgs/settings.ot.example" "$INSTALL_DIR/cfgs/settings.ini"
fi

# Set executable permissions on scripts
chmod +x "$INSTALL_DIR/menu.py" "$INSTALL_DIR/runvpn.sh"
chmod +x "$INSTALL_DIR/install.sh" "$INSTALL_DIR/uninstall.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/vpn/"* 2>/dev/null || true

# ------------------------------------------------------------------------------
# 6. Create Terminal Command 'otunnel'
# ------------------------------------------------------------------------------
echo -e "\n${C_BLUE}[*] Creating system launcher command: $BIN_LINK...${C_RESET}"

cat << 'EOF' > "$BIN_LINK"
#!/usr/bin/env bash
INSTALL_DIR="/opt/omnitunnel-cli"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: OmniTunnel CLI directory not found at $INSTALL_DIR" >&2
    exit 1
fi

cd "$INSTALL_DIR" || exit 1

if [ "$EUID" -ne 0 ]; then
    exec sudo python3 "$INSTALL_DIR/menu.py" "$@"
else
    exec python3 "$INSTALL_DIR/menu.py" "$@"
fi
EOF

chmod +x "$BIN_LINK"
echo -e "${C_GREEN}[✔] Launcher created: $BIN_LINK -> $INSTALL_DIR/menu.py${C_RESET}"

# ------------------------------------------------------------------------------
# 7. Complete
# ------------------------------------------------------------------------------
echo -e "\n${C_GREEN}${C_BOLD}======================================================${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}  OmniTunnel CLI has been successfully installed!     ${C_RESET}"
echo -e "${C_GREEN}${C_BOLD}======================================================${C_RESET}"
echo -e "\nYou can now launch OmniTunnel from anywhere by running:"
echo -e "  ${C_CYAN}${C_BOLD}otunnel${C_RESET}  (or  ${C_CYAN}${C_BOLD}sudo otunnel${C_RESET})\n"
echo -e "To uninstall anytime, run:"
echo -e "  ${C_YELLOW}curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/uninstall.sh | sudo bash${C_RESET}\n"

