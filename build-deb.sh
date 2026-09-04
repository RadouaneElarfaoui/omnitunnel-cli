#!/bin/bash
set -euo pipefail

IMAGE="omnitunnel-deb-build"
CONTAINER="omnitunnel-build-container"
VERSION="1.1.0"
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

cat > "${CTRL_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e
ID="/opt/omnitunnel-cli"
mkdir -p "${ID}/bin" "${ID}/logs" "${ID}/cfgs/saved"
touch "${ID}/cfgs/saved/.gitkeep"
chmod 777 "${ID}/cfgs" "${ID}/logs"
if ! command -v sing-box &>/dev/null; then
    echo "Note: sing-box not found. Install it manually:"
    echo "  wget https://github.com/SagerNet/sing-box/releases/download/v1.14.0/sing-box_1.14.0_linux_amd64.deb"
    echo "  sudo dpkg -i ./sing-box_1.14.0_linux_amd64.deb"
fi
POSTINST
chmod 755 "${CTRL_DIR}/DEBIAN/postinst"

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
    -v "${CTRL_DIR}/DEBIAN:/ctrl:ro" \
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

chmod 755 "${PKGDIR}/opt/omnitunnel-cli/runvpn.sh"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/menu.py"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/main.py"
chmod 755 "${PKGDIR}/opt/omnitunnel-cli/ConfMake"
find "${PKGDIR}/opt/omnitunnel-cli/vpn/" -type f -exec chmod 755 {} +

cp /ctrl/control   "${PKGDIR}/DEBIAN/control"
cp /ctrl/postinst  "${PKGDIR}/DEBIAN/postinst"
cp /ctrl/prerm     "${PKGDIR}/DEBIAN/prerm"

mkdir -p "${PKGDIR}/usr/share/applications"
mkdir -p "${PKGDIR}/usr/share/icons/hicolor/scalable/apps"
mv "${PKGDIR}/opt/omnitunnel-cli/omnitunnel-cli.desktop" "${PKGDIR}/usr/share/applications/"
mv "${PKGDIR}/opt/omnitunnel-cli/omnitunnel-cli.svg" "${PKGDIR}/usr/share/icons/hicolor/scalable/apps/"

dpkg-deb --root-owner-group --build "${PKGDIR}"
cp "${PKGDIR}"*.deb /output/
echo "==> Built debs in /output/"
'

rm -rf "${CTRL_DIR}"
echo "==> Build complete: ${OUTPUT_DIR}/${DEB_FILE}"
ls -lh "${OUTPUT_DIR}/${DEB_FILE}"
