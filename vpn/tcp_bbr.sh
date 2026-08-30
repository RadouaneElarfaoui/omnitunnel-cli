#!/usr/bin/env bash
# TCP BBR Optimization Script for OmniTunnel CLI

if [ "$EUID" -ne 0 ]; then
  echo "✕ Error: TCP BBR optimization requires root privileges. Please run with sudo."
  exit 1
fi

echo "=========================================="
echo " OmniTunnel CLI - Kernel TCP BBR Tuning "
echo "=========================================="

CURRENT_CC=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)

echo "Current TCP Congestion Control: ${CURRENT_CC}"

if [ "$CURRENT_CC" = "bbr" ]; then
    echo "✔ TCP BBR is already enabled and active on this system!"
    exit 0
fi

echo "Enabling TCP BBR..."
sysctl -w net.core.default_qdisc=fq
sysctl -w net.ipv4.tcp_congestion_control=bbr

# Make settings persistent in /etc/sysctl.d/99-omnitunnel-bbr.conf
cat <<'EOF' > /etc/sysctl.d/99-omnitunnel-bbr.conf
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF

sysctl -p /etc/sysctl.d/99-omnitunnel-bbr.conf 2>/dev/null

NEW_CC=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)
if [ "$NEW_CC" = "bbr" ]; then
    echo "✔ TCP BBR optimization successfully activated!"
else
    echo "⚠ Could not enable BBR (Kernel BBR module might not be compiled in your kernel)."
fi
