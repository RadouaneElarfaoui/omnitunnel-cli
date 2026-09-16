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
# wget -c: resumable + progress bar. curl kept as fallback (also resumable via -C -).
if command -v wget >/dev/null 2>&1; then
    wget -c --show-progress --progress=bar:force -P "$TMP_DIR" "$BASE_URL/$TARBALL"
    wget -q -O "$TMP_DIR/SHA256SUMS" "$BASE_URL/SHA256SUMS"
elif command -v curl >/dev/null 2>&1; then
    curl -fSL -C - --progress-bar -o "$TMP_DIR/$TARBALL" "$BASE_URL/$TARBALL"
    curl -fsSL -o "$TMP_DIR/SHA256SUMS" "$BASE_URL/SHA256SUMS"
else
    echo -e "${RED}[✕] Need wget or curl to download sing-box-lx.${NC}"
    exit 1
fi

echo -e "${BLUE}[*] Verifying checksum...${NC}"
(cd "$TMP_DIR" && grep "  $TARBALL\$" SHA256SUMS > sha.want) || {
    echo -e "${RED}[✕] Checksum entry for $TARBALL not found in upstream SHA256SUMS.${NC}"
    exit 1
}
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$TMP_DIR" && sha256sum -c sha.want) || exit 1
elif command -v shasum >/dev/null 2>&1; then
    (cd "$TMP_DIR" && shasum -a 256 -c sha.want) || exit 1
else
    echo -e "${RED}[✕] Need sha256sum or shasum to verify the download.${NC}"
    exit 1
fi

echo -e "${BLUE}[*] Installing to $INSTALL_DIR...${NC}"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
tar -xzf "$TMP_DIR/$TARBALL" -C "$TMP_DIR"
# Release tarballs contain a single top-level sing-box binary (plus docs).
BIN_SRC="$(find "$TMP_DIR" -maxdepth 2 -type f -name 'sing-box' | head -n 1)"
if [ -z "$BIN_SRC" ]; then
    echo -e "${RED}[✕] sing-box binary not found inside $TARBALL.${NC}"
    exit 1
fi
cp "$BIN_SRC" "$INSTALL_DIR/sing-box"
chmod 755 "$INSTALL_DIR/sing-box"
ln -sf "$INSTALL_DIR/sing-box" "$BIN_LINK"

echo -e "${BLUE}[*] Verifying installation...${NC}"
INSTALLED="$("$BIN_LINK" version 2>/dev/null | head -n 1)"
if ! echo "$INSTALLED" | grep -q "lx"; then
    echo -e "${RED}[✕] Installed binary does not report an -lx version: $INSTALLED${NC}"
    exit 1
fi
echo -e "${GREEN}[✔] sing-box-lx installed: $BIN_LINK ($INSTALLED)${NC}"
echo -e "    OmniTunnel will use it automatically for xhttp profiles once wired as an engine."
