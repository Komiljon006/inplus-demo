#!/usr/bin/env bash
# systemd unit'larni /etc/systemd/system ga o'rnatadi (Linux server).
# Mac'da systemd yo'q — demo `bin/inplus ishga <AGENT>` bilan ishlaydi.
set -euo pipefail
HOZIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(uname)" = "Darwin" ]; then
  echo "Mac: systemd yo'q. 'bin/inplus ishga <AGENT>' ishlating."
  exit 0
fi
for f in "$HOZIR"/*.service "$HOZIR"/*.timer; do
  [ -e "$f" ] || continue
  sudo cp "$f" /etc/systemd/system/
  echo "  o'rnatildi: $(basename "$f")"
done
sudo systemctl daemon-reload
echo "Yoqish: sudo systemctl enable --now inplus-d6.timer inplus-d1.timer \\"
echo "        inplus-n3.timer inplus-x1.timer inplus-w1.timer inplus-x0.timer"
echo "Servislar: sudo systemctl enable --now inplus-shlyuz inplus-x2"
