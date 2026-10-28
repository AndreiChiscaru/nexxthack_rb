#!/usr/bin/env bash
# Usage: check_game.sh <statement.pdf> — checks that the game is served and that /api/analyze returns a game profile.
set -uo pipefail
BASE=http://127.0.0.1:8787

for path in /joc /joc/ /joc/index.wasm /joc/index.pck /; do
  curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}B $path\n" "$BASE$path"
done
if [ -n "${1:-}" ]; then
  curl -s -o /tmp/analyze.json -w "analyze HTTP %{http_code} in %{time_total}s\n" -F "file=@$1" "$BASE/api/analyze"
fi
