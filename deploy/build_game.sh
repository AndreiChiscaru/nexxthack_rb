#!/usr/bin/env bash
# Runs on the server: installs headless Godot, runs the game test suite and exports the web build to /opt/extras/game.
set -euo pipefail

APP_DIR=/opt/extras
SRC_DIR=$APP_DIR/raiffquest
OUT_DIR=$APP_DIR/game
GODOT_HOME=/opt/godot
GODOT_MINOR=${GODOT_MINOR:-4.7}

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q unzip libfontconfig1 >/dev/null

if [ ! -x "$GODOT_HOME/godot" ]; then
  TAG=$(curl -fsS "https://api.github.com/repos/godotengine/godot/releases?per_page=30" | python3 -c "
import json, sys
tags = [r['tag_name'] for r in json.load(sys.stdin) if r['tag_name'].startswith('$GODOT_MINOR') and not r['prerelease']]
print(tags[0] if tags else '')")
  if [ -z "$TAG" ]; then echo "Nu am gasit Godot $GODOT_MINOR stable" >&2; exit 1; fi
  echo ">>> Instalez Godot $TAG"
  BASE="https://github.com/godotengine/godot/releases/download/$TAG"
  TMP=$(mktemp -d)
  curl -fsSL -o "$TMP/godot.zip" "$BASE/Godot_v${TAG}_linux.arm64.zip"
  curl -fsSL -o "$TMP/templates.tpz" "$BASE/Godot_v${TAG}_export_templates.tpz"
  sudo mkdir -p "$GODOT_HOME" && sudo chown ubuntu:ubuntu "$GODOT_HOME"
  unzip -q -o "$TMP/godot.zip" -d "$GODOT_HOME"
  mv "$GODOT_HOME"/Godot_v*_linux.arm64 "$GODOT_HOME/godot"
  TEMPLATE_DIR="$HOME/.local/share/godot/export_templates/${TAG/-/.}"
  mkdir -p "$TEMPLATE_DIR"
  unzip -q -o "$TMP/templates.tpz" "templates/web_*" -d "$TMP/t"
  mv "$TMP"/t/templates/* "$TEMPLATE_DIR/"
  rm -rf "$TMP"
fi
GODOT="$GODOT_HOME/godot"
"$GODOT" --version

cd "$SRC_DIR"
echo ">>> Import resurse"
timeout 300 "$GODOT" --headless --path . --import >/dev/null 2>&1 || true

echo ">>> Teste"
for scene in journey_boot_test city_map_test stat_hud_test; do
  TEST_LOG=$(mktemp)
  if ! timeout 300 "$GODOT" --headless --path . "res://test/${scene}.tscn" >"$TEST_LOG" 2>&1; then
    cat "$TEST_LOG"; rm -f "$TEST_LOG"; exit 1
  fi
  cat "$TEST_LOG"
  if grep -Eq "SCRIPT ERROR|Parse Error|ERROR" "$TEST_LOG" || ! grep -q "PASS" "$TEST_LOG"; then
    rm -f "$TEST_LOG"; exit 1
  fi
  rm -f "$TEST_LOG"
done

echo ">>> Export web"
rm -rf "$SRC_DIR/dist" && mkdir -p "$SRC_DIR/dist"
timeout 600 "$GODOT" --headless --path . --export-release Web dist/index.html 2>&1 | tail -5
test -f dist/index.html
# AudioWorklet exists on the prototype but is undefined on http://IP, and Godot
# calls it during startup. Skip it there; the script-processor driver still plays.
python3 - <<'PY'
from pathlib import Path
p = Path("dist/index.js")
t = p.read_text()
a = "GodotAudio.audioPositionWorkletPromise=ctx.audioWorklet.addModule(path);"
b = "GodotAudio.audioPositionWorkletPromise=(ctx.audioWorklet?ctx.audioWorklet.addModule(path):Promise.resolve());"
c = "async connectPositionWorklet(start){await GodotAudio.audioPositionWorkletPromise;if(this.isCanceled){return}this._source.connect(this.getPositionWorklet());if(start){this.start()}}"
d = "async connectPositionWorklet(start){if(!GodotAudio.ctx||!GodotAudio.ctx.audioWorklet){if(start&&!this.isCanceled){this.start()}return}await GodotAudio.audioPositionWorkletPromise;if(this.isCanceled){return}this._source.connect(this.getPositionWorklet());if(start){this.start()}}"
if a not in t or c not in t:
    raise SystemExit("patch audio: pattern missing")
p.write_text(t.replace(a, b, 1).replace(c, d, 1))
print("patch audio: ok")
PY
rm -rf "$OUT_DIR" && mv dist "$OUT_DIR"
ls -la "$OUT_DIR"
sudo systemctl restart extras
