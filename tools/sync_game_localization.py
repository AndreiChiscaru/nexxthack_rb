"""Copy reviewed game translations into the resource included in Godot web exports.
Run with --check in CI to detect a stale exported catalog.
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/localization/en.json"
TARGET = ROOT / "raiffquest/localization/game_en.json"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = SOURCE.read_bytes()
    if args.check:
        if not TARGET.exists() or TARGET.read_bytes() != source:
            raise SystemExit("Godot catalog is stale: run python tools/sync_game_localization.py")
        print("Localization catalogs match")
    else:
        TARGET.write_bytes(source)
        print("Godot localization catalog updated")
