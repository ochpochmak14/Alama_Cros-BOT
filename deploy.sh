#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ubuntu/alamacros/Alama_Cros-BOT"
ENV_FILE="/etc/alamacros-bot.env"
SERVICE="alamacros-bot"

cd "$APP_DIR"

echo "== 1) Update code =="
git pull

echo "== 2) Install deps =="
./venv/bin/pip install -r requirements.txt

echo "== 3) Run migrations (if exist) =="
if [ -f "$APP_DIR/migrate.sh" ]; then
  sudo bash -c "set -a; source $ENV_FILE; set +a; cd $APP_DIR; ./migrate.sh"
else
  echo "No migrate.sh found, skipping."
fi

echo "== 4) Restart service =="
sudo systemctl restart "$SERVICE"

echo "== 5) Status =="
sudo systemctl status "$SERVICE" --no-pager
