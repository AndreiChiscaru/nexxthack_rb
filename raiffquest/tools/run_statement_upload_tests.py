"""Run the native uploader against a local multipart fixture with synthetic bytes."""
import argparse
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length']))
        message = BytesParser(policy=default).parsebytes(
            ('Content-Type: ' + self.headers['Content-Type'] + '\r\n\r\n').encode() + raw)
        parts = {part.get_param('name', header='content-disposition'): part for part in message.iter_parts()}
        verified = (self.path == '/api/onboarding/statement'
                    and set(parts) == {'session_id', 'file'}
                    and parts['session_id'].get_payload(decode=True) == b'fixture-session'
                    and parts['file'].get_filename() == 'statement-upload-test.txt'
                    and parts['file'].get_payload(decode=True) == b'Synthetic statement only')
        body = json.dumps({'verified': verified}).encode()
        self.send_response(200 if verified else 422)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        result = subprocess.run([args.godot, '--headless', '--path', str(Path(__file__).resolve().parents[1]),
                                 'res://test/statement_upload_test.tscn'],
                                env=dict(os.environ, RAIFF_UPLOAD_TEST_API=f'http://127.0.0.1:{server.server_port}'), timeout=60)
        server.shutdown()
        raise SystemExit(result.returncode)

