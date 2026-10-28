"""Test the Godot API client against the team's actual local FastAPI app.

Requires the repository's requirements.txt. Starts an isolated server on a free
loopback port, uses synthetic profile data, and makes no LLM or bank API calls.
"""
import argparse
import gc
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default="godot")
    parser.add_argument("--scene", default="res://test/backend_contract_test.tscn")
    parser.add_argument("--visible", action="store_true", help="Render the integration scene for visual QA")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="raiff-frontend-test-") as temporary:
        os.environ["DEMO_DB"] = str(Path(temporary) / "demo.sqlite3")
        return run_test(args.godot, args.scene, args.visible)


def run_test(godot, scene, visible=False):
    # The real onboarding now calls Claude when credentials are configured.
    os.environ["MOCK_LLM"] = "true"
    import uvicorn

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("The local backend did not start; inspect the error above.")
                time.sleep(0.05)
            env = dict(os.environ, RAIFF_TEST_API=f"http://127.0.0.1:{port}")
            result = subprocess.run(
                [godot, *([] if visible else ["--headless"]), "--path", str(ROOT), scene],
                env=env, timeout=60, check=False,
            )
            return result.returncode
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            # The demo store leaves SQLite connections for garbage collection.
            # Release their file handles before TemporaryDirectory cleans up on Windows.
            gc.collect()


if __name__ == "__main__":
    raise SystemExit(main())
