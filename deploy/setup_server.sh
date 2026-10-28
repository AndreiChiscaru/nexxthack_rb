#!/usr/bin/env bash
# Runs on the Ubuntu server, from the uploaded project directory (/opt/extras).
set -euo pipefail

APP_DIR=/opt/extras
cd "$APP_DIR"

sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip nginx \
  tesseract-ocr tesseract-ocr-ron tesseract-ocr-eng

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ">>> Completează ANTHROPIC_API_KEY în $APP_DIR/.env"
fi
chmod 600 .env

sudo cp deploy/extras.service /etc/systemd/system/extras.service
sudo systemctl daemon-reload
sudo systemctl enable --now extras
sudo systemctl restart extras

sudo cp deploy/nginx.conf /etc/nginx/sites-available/extras
sudo ln -sf /etc/nginx/sites-available/extras /etc/nginx/sites-enabled/extras
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

# Oracle Cloud Ubuntu images block port 80 in iptables by default.
for PORT in 80 8787; do
  while sudo iptables -D INPUT -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; do :; done
  REJECT_POS=$(sudo iptables -L INPUT --line-numbers -n | awk '$2=="REJECT"{print $1; exit}')
  sudo iptables -I INPUT "${REJECT_POS:-1}" -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT
done
if command -v netfilter-persistent >/dev/null; then sudo netfilter-persistent save; fi

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1/api/health; then echo; echo ">>> Deploy OK"; exit 0; fi
  sleep 2
done
echo ">>> Serviciul nu raspunde; vezi: sudo journalctl -u extras -n 50" >&2
exit 1
