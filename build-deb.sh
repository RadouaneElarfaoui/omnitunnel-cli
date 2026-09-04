#!/bin/bash
set -euo pipefail

IMAGE="omnitunnel-deb-build"
CONTAINER="omnitunnel-build-container"
VERSION="1.1.5"
ARCH="amd64"
PKG_NAME="omnitunnel-cli"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
DEB_FILE="${PKG_NAME}_${VERSION}.deb"

echo "==> Cleaning previous build..."
podman rm -f "${CONTAINER}" 2>/dev/null || true
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

echo "==> Building container image..."
podman build -t "${IMAGE}" -f - "${SCRIPT_DIR}" <<'DOCKERFILE'
FROM debian:trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    dpkg-dev rsync \
    && rm -rf /var/lib/apt/lists/*
DOCKERFILE

echo "==> Writing control files..."
CTRL_DIR=$(mktemp -d)
mkdir -p "${CTRL_DIR}/DEBIAN"

cat > "${CTRL_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Depends: openssh-client, sshpass, netcat-openbsd, python3 (>= 3.11), python3-certifi
Recommends: sing-box
Maintainer: Radouane Elarfaoui <dev@omnitunnel-cli>
Homepage: https://github.com/RadouaneElarfaoui/omnitunnel-cli
Description: CLI VPN client based on SSH tunnels and V2Ray/Xray protocols
 OmniTunnel CLI is a command-line VPN client based on SSH tunnels,
 V2Ray/Xray protocols, and HTTP payload injection, designed to bypass
 network restrictions under Linux (Ubuntu/Debian) and Android (Termux).
 Supports V2Ray/Xray share links, Sing-Box TUN engine, encrypted .ot
 profiles, and kernel TCP BBR optimization.
EOF

# Wrapper is written once on the host (quoted heredoc, no expansion issues)
# and reused both in postinst and inside the container payload.
cat > "${CTRL_DIR}/otunnel" <<'WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/opt/omnitunnel-cli"
cd "$INSTALL_DIR" || exit 1
exec python3 "$INSTALL_DIR/menu.py" "$@"
WRAPPER
chmod 755 "${CTRL_DIR}/otunnel"

cat > "${CTRL_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e
ID="/opt/omnitunnel-cli"
mkdir -p "${ID}/bin" "${ID}/logs" "${ID}/cfgs/saved"
touch "${ID}/cfgs/saved/.gitkeep"
chmod 777 "${ID}/cfgs" "${ID}/cfgs/saved" "${ID}/logs"
# Launcher wrapper (also shipped as /usr/local/bin/otunnel inside the .deb;
# re-created here so upgrades/repairs always leave a working entry point).
cat > /usr/local/bin/otunnel <<'OTUNNEL_WRAPPER'
#!/usr/bin/env bash
INSTALL_DIR="/opt/omnitunnel-cli"
cd "$INSTALL_DIR" || exit 1
exec python3 "$INSTALL_DIR/menu.py" "$@"
OTUNNEL_WRAPPER
chmod 755 /usr/local/bin/otunnel
# The desktop session runs as an unprivileged user, so the launcher entry
# and icon MUST stay world-readable (0644), otherwise the app is invisible.
chmod 644 /usr/share/applications/omnitunnel-cli.desktop 2>/dev/null || true
chmod 644 /usr/share/icons/hicolor/scalable/apps/omnitunnel-cli.svg 2>/dev/null || true
if ! command -v sing-box &>/dev/null; then
    echo "Note: sing-box not found. Install it manually:"
    echo "  wget https://github.com/SagerNet/sing-box/releases/download/v1.14.0/sing-box_1.14.0_linux_amd64.deb"
    echo "  sudo dpkg -i ./sing-box_1.14.0_linux_amd64.deb"
fi
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
POSTINST
chmod 755 "${CTRL_DIR}/DEBIAN/postinst"

cat > "${CTRL_DIR}/DEBIAN/postrm" <<'POSTRM'
#!/bin/bash
set -e
# Refresh launcher/icon caches on remove/purge so the entry disappears cleanly.
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
POSTRM
chmod 755 "${CTRL_DIR}/DEBIAN/postrm"

cat > "${CTRL_DIR}/DEBIAN/prerm" <<'PRERM'
#!/bin/bash
set -e
ID="/opt/omnitunnel-cli"
pkill -f "python3 ${ID}/main.py" 2>/dev/null || true
pkill -f "python3 ${ID}/src/ssh.py" 2>/dev/null || true
pkill -f "sshpass.*host1" 2>/dev/null || true
pkill -f "ssh.*-CND 1080" 2>/dev/null || true
PRERM
chmod 755 "${CTRL_DIR}/DEBIAN/prerm"

echo "==> Running build inside container..."
podman run --rm --name "${CONTAINER}" \
    -v "${SCRIPT_DIR}:/src:ro" \
    -v "${OUTPUT_DIR}:/output" \
    -v "${CTRL_DIR}:/ctrl:ro" \
    "${IMAGE}" \
    bash -c '
set -euo pipefail
VERSION="'"${VERSION}"'"
ARCH="'"${ARCH}"'"
PKG_NAME="'"${PKG_NAME}"'"
WORKDIR=/tmp/build
rm -rf "${WORKDIR}"
PKGDIR="${WORKDIR}/${PKG_NAME}_${VERSION}"
mkdir -p "${PKGDIR}/DEBIAN"
mkdir -p "${PKGDIR}/opt/omnitunnel-cli"

rsync -a --no-perms --no-owner --no-group \
    --exclude=".git" --exclude="__pycache__" --exclude="bin/" --exclude="logs/" \
    --exclude="dist/" --exclude="build-deb.sh" --exclude="*.deb" \
    /src/ "${PKGDIR}/opt/omnitunnel-cli/"

mkdir -p "${PKGDIR}/opt/omnitunnel-cli/bin"
mkdir -p "${PKGDIR}/opt/omnitunnel-cli/cfgs/saved"
mkdir -p "${PKGDIR}/opt/omnitunnel-cli/logs"
touch "${PKGDIR}/opt/omnitunnel-cli/cfgs/saved/.gitkeep"

# Normalize permissions: the desktop session is unprivileged, so everything
# under /opt must be world-readable/traversable (source checkouts often
# carry 600/700 modes which would break imports AND hide the launcher entry).
find "${PKGDIR}/opt/omnitunnel-cli" -type d -exec chmod 755 {} +
chmod 777 "${PKGDIR}/opt/omnitunnel-cli/cfgs" "${PKGDIR}/opt/omnitunnel-cli/cfgs/saved" "${PKGDIR}/opt/omnitunnel-cli/logs"
find "${PKGDIR}/opt/omnitunnel-cli" -type f -exec chmod 644 {} +

chmod 755 "${PKGDIR}/opt/omnitunnel-cli/runvpn.sh"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/menu.py"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/main.py"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/ConfMake"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/install.sh" "${PKGDIR}/opt/omnitunnel-cli/uninstall.sh" || true
find "${PKGDIR}/opt/omnitunnel-cli/vpn/" -type f -exec chmod 755 {} +

# Terminal launcher used by the .desktop Exec= line (written on the host
# to avoid nested-heredoc quoting issues inside this bash -c string).
mkdir -p "${PKGDIR}/usr/local/bin"
cp /ctrl/otunnel "${PKGDIR}/usr/local/bin/otunnel"
chmod 755 "${PKGDIR}/usr/local/bin/otunnel"

cp /ctrl/DEBIAN/control   "${PKGDIR}/DEBIAN/control"
cp /ctrl/DEBIAN/postinst  "${PKGDIR}/DEBIAN/postinst"
cp /ctrl/DEBIAN/postrm    "${PKGDIR}/DEBIAN/postrm"
cp /ctrl/DEBIAN/prerm     "${PKGDIR}/DEBIAN/prerm"

mkdir -p "${PKGDIR}/usr/share/applications"
mkdir -p "${PKGDIR}/usr/share/icons/hicolor/scalable/apps"
mv "${PKGDIR}/opt/omnitunnel-cli/omnitunnel-cli.desktop" "${PKGDIR}/usr/share/applications/"
mv "${PKGDIR}/opt/omnitunnel-cli/omnitunnel-cli.svg" "${PKGDIR}/usr/share/icons/hicolor/scalable/apps/"
chmod 644 "${PKGDIR}/usr/share/applications/omnitunnel-cli.desktop"
chmod 644 "${PKGDIR}/usr/share/icons/hicolor/scalable/apps/omnitunnel-cli.svg"

dpkg-deb --root-owner-group --build "${PKGDIR}"
cp "${PKGDIR}"*.deb /output/
echo "==> Built debs in /output/"
'

rm -rf "${CTRL_DIR}"
echo "==> Build complete: ${OUTPUT_DIR}/${DEB_FILE}"
ls -lh "${OUTPUT_DIR}/${DEB_FILE}"
