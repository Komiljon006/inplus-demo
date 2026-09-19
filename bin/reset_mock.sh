#!/usr/bin/env bash
# data/ ni tozalaydi va mock ni --kun 0 bilan qayta yasaydi.
set -euo pipefail
ILDIZ="${INPLUS_ILDIZ:-$(cd "$(dirname "$0")/.." && pwd)}"
echo "data/ tozalanmoqda: $ILDIZ/data"
rm -rf "$ILDIZ/data" "$ILDIZ/run/heartbeat"
mkdir -p "$ILDIZ/data" "$ILDIZ/run/heartbeat"
python3 "$ILDIZ/mock/generator.py" --kun 0
echo "tayyor."
