#!/bin/bash
# Install sing-box-lx (sing-box fork with XHTTP transport) for OmniTunnel CLI.
#
# Opt-in engine for Xray-style xhttp:// links, which stock sing-box cannot
# speak. Installs side-by-side with upstream sing-box — never replaces it:
#   binary : /usr/local/bin/sing-box-lx  (-> /opt/singbox-lx/<tag>/sing-box)
#
# One-liner (needs sudo for /opt and /usr/local/bin):
#   curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/install-singbox-lx.sh | sudo bash
# Termux (no sudo, PREFIX-aware):
#   bash install-singbox-lx.sh
set -euo pipefail

SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

LX_VERSION="${LX_VERSION:-v1.14.1-lx.3}"
REPO="${LX_REPO:-Leadaxe/sing-box-lx}"

# PREFIX-aware layout (Termux sets PREFIX; otherwise FHS).
if [ -n "${PREFIX:-}" ]; then
    OPT_ROOT="$PREFIX/opt"
    BIN_DIR="$PREFIX/bin"
else
    OPT_ROOT="/opt"
    BIN_DIR="/usr/local/bin"
fi
INSTALL_DIR="$OPT_ROOT/singbox-lx/$LX_VERSION"
BIN_LINK="$BIN_DIR/sing-box-lx"

RED='\033[1;31m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; BLUE='\033[1;34m'; NC='\033[0m'

# Idempotent: pinned version already linked → nothing to do.
if [ -x "$BIN_LINK" ]; then
    INSTALLED="$("$BIN_LINK" version 2>/dev/null | head -n 1 || true)"
    if echo "$INSTALLED" | grep -q "$LX_VERSION"; then
        echo -e "${GREEN}[✔] sing-box-lx $LX_VERSION already installed at $BIN_LINK — skipping.${NC}"
        exit 0
    fi
    echo -e "${YELLOW}[!] Different sing-box-lx present ($INSTALLED) — upgrading to $LX_VERSION.${NC}"
fi

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)          LX_ARCH="amd64" ;;
    aarch64|arm64)   LX_ARCH="arm64" ;;
    armv7l|armhf)    LX_ARCH="armv7" ;;
    *) echo -e "${RED}[✕] Unsupported architecture for sing-box-lx: $ARCH${NC}"; exit 1 ;;
esac

BASE_URL="https://github.com/${REPO}/releases/download/${LX_VERSION}"
TARBALL="sing-box-${LX_VERSION#v}-linux-${LX_ARCH}.tar.gz"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo -e "${BLUE}[*] Downloading sing-box-lx $LX_VERSION ($LX_ARCH)...${NC}"
if ! command -v wget >/dev/null 2>&1; then
    echo -e "${RED}[✕] Need wget to download sing-box-lx.${NC}"
    exit 1
fi
wget -c -P /tmp/ "$BASE_URL/$TARBALL"
wget -q -O "$TMP_DIR/SHA256SUMS" "$BASE_URL/SHA256SUMS"
DL_FILE="/tmp/$TARBALL"

echo -e "${BLUE}[*] Verifying checksum...${NC}"
echo "$(grep "  $TARBALL\$" "$TMP_DIR/SHA256SUMS" | cut -d' ' -f1)  $DL_FILE" | sha256sum -c -

echo -e "${BLUE}[*] Installing to $INSTALL_DIR...${NC}"
$SUDO mkdir -p "$INSTALL_DIR" "$BIN_DIR"
tar -xzf "$DL_FILE" -C "$TMP_DIR"
# Release tarballs contain a single top-level sing-box binary (plus docs).
BIN_SRC="$(find "$TMP_DIR" -maxdepth 2 -type f -name 'sing-box' | head -n 1)"
if [ -z "$BIN_SRC" ]; then
    echo -e "${RED}[✕] sing-box binary not found inside $TARBALL.${NC}"
    exit 1
fi
$SUDO cp "$BIN_SRC" "$INSTALL_DIR/sing-box"
$SUDO chmod 755 "$INSTALL_DIR/sing-box"
$SUDO ln -sf "$INSTALL_DIR/sing-box" "$BIN_LINK"

echo -e "${BLUE}[*] Verifying installation...${NC}"
INSTALLED="$("$BIN_LINK" version 2>/dev/null | head -n 1)"
if ! echo "$INSTALLED" | grep -q "lx"; then
    echo -e "${RED}[✕] Installed binary does not report an -lx version: $INSTALLED${NC}"
    exit 1
fi
echo -e "${GREEN}[✔] sing-box-lx installed: $BIN_LINK ($INSTALLED)${NC}"
echo -e "    OmniTunnel uses it automatically for xhttp profiles (Edit → Engine)."
# Verified install: drop the cached tarball, keep the dir for next time.
rm -f "$DL_FILE"
