#!/usr/bin/env bash
# Serverda (Linux) systemd unit'larni o'rnatadi. Mac'da KERAK EMAS (bin/inplus ishga).
set -euo pipefail
ILDIZ="${INPLUS_ILDIZ:-/opt/inplus}"

if [ "$(uname)" = "Darwin" ]; then
  echo "Mac aniqlangan — systemd yo'q. Demo: 'bin/inplus ishga <AGENT>' bilan ishlating."
  exit 0
fi

echo "systemd unit'lar $ILDIZ/systemd -> /etc/systemd/system"
for f in "$ILDIZ"/systemd/*.service "$ILDIZ"/systemd/*.timer; do
  [ -e "$f" ] || continue
  sudo cp "$f" /etc/systemd/system/
done
sudo systemctl daemon-reload
echo "daemon-reload bajarildi. Yoqish: systemctl enable --now inplus-d6.timer ..."
