"""Offline checks for the current game; no Manus runtime needed."""
import argparse
from pathlib import Path
import subprocess
parser = argparse.ArgumentParser()
parser.add_argument("--godot", default="godot")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
for scene in ("journey_boot_test", "city_map_test", "stat_hud_test"):
    result = subprocess.run([args.godot, "--headless", "--path", str(root), f"res://test/{scene}.tscn"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    output = result.stdout + result.stderr
    print(output)
    if result.returncode or "PASS" not in output or "SCRIPT ERROR" in output or "ERROR:" in output:
        raise SystemExit(1)
