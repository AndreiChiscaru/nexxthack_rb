#!/usr/bin/env bash
# Exposes the app over HTTPS through a Cloudflare quick tunnel (Godot web builds need a secure context).
# The trycloudflare.com URL changes whenever the service restarts; read it with: bash setup_tunnel.sh url
set -euo pipefail

if [ "${1:-}" = "url" ]; then
  sudo journalctl -u extras-tunnel --no-pager | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
  exit 0
fi

if ! command -v cloudflared >/dev/null; then
  TMP=$(mktemp -d)
  curl -fsSL -o "$TMP/cloudflared.deb" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
  sudo dpkg -i "$TMP/cloudflared.deb" >/dev/null
  rm -rf "$TMP"
fi

sudo tee /etc/systemd/system/extras-tunnel.service >/dev/null <<'EOF'
[Unit]
Description=Cloudflare quick tunnel for extras (HTTPS)
After=network-online.target extras.service
Wants=network-online.target

[Service]
User=ubuntu
ExecStart=/usr/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8787
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable extras-tunnel >/dev/null 2>&1
sudo systemctl restart extras-tunnel
for _ in $(seq 1 30); do
  URL=$(sudo journalctl -u extras-tunnel --no-pager --since "-2min" | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1 || true)
  if [ -n "$URL" ]; then echo "$URL"; exit 0; fi
  sleep 2
done
echo "Tunelul nu a pornit; vezi: sudo journalctl -u extras-tunnel -n 50" >&2
exit 1
