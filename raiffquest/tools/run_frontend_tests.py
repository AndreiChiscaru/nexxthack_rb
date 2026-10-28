"""Run frontend HTTP integration tests against an ephemeral local fixture.

Uses Python's standard library. Does not start or modify the real backend.
Usage: python tools/run_frontend_tests.py --godot /path/to/godot
"""
import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
COUNTS = Counter()
LOCK = threading.Lock()


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        url = urlsplit(self.path)
        with LOCK:
            COUNTS[(self.command, url.path)] += 1
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        data = {"path": url.path, "query": parse_qs(url.query), "body": json.loads(body) if body else {}}
        status = 200
        if url.path == "/api/session":
            data = {"session_id": "fixture-session"}
        elif url.path == "/api/invalid-shape":
            data = "unexpected scalar"
        elif url.path == "/api/failure":
            status, data = 503, {"detail": "Serviciu indisponibil"}
        elif url.path == "/api/validation":
            status, data = 422, {"detail": [{"loc": ["body", "session_id"], "msg": "Field required"}]}
        elif url.path == "/api/slow":
            time.sleep(1.2)
        elif url.path == "/api/delay":
            time.sleep(0.6)
        elif url.path == "/api/stats":
            with LOCK:
                data = {"slow_posts": COUNTS[("POST", "/api/slow")]}
        elif url.path == "/api/no-content":
            status = 204
        elif url.path == "/api/large":
            data = {"text": "x" * (2 * 1024 * 1024 + 1)}
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if url.path == "/api/invalid-json":
            raw = b"<html>not json</html>"
        if status == 204:
            raw = b""
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Expected for timeout, cancellation, and response-size tests.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default="godot")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = dict(os.environ, RAIFF_TEST_API=f"http://127.0.0.1:{server.server_port}")
        env.pop("RAIFF_API", None)
        try:
            result = subprocess.run(
                [args.godot, "--headless", "--path", str(ROOT), "res://test/frontend_api_test.tscn"],
                env=env, timeout=60, check=False,
            )
            return result.returncode
        finally:
            server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
