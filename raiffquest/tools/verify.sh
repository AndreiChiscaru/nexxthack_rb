#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/tools/verify_current.py" --godot "${GODOT:-godot}"
if [[ "${1:-}" == "--export" ]]; then
  mkdir -p "$ROOT/dist"
  "${GODOT:-godot}" --headless --path "$ROOT" --export-release Web "$ROOT/dist/index.html"
fi
