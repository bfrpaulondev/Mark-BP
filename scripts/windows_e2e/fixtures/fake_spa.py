"""Local fake SPA + download fixture for browser physical E2E (ANT-275 C5).

Standard-library HTTP server, no internet dependency:

- GET /            → SPA page: a button that switches the in-page route
  (updates DOM + location.hash) and a download link;
- GET /download    → small generated text file (download case);
- GET /health      → liveness for the runner.

Usage (physical machine only):
    python scripts/windows_e2e/fixtures/fake_spa.py --port 8765
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Antonella E2E SPA</title></head>
<body>
  <h1 id="route-label">home</h1>
  <button id="nav" onclick="location.hash='#/settings';
    document.getElementById('route-label').textContent='settings';">
    go to settings</button>
  <a id="dl" href="/download">download</a>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/health":
            self._send(200, b"ok", "text/plain")
        elif self.path == "/download":
            body = b"antonella e2e synthetic download\n" * 16
            self._send(
                200,
                body,
                "application/octet-stream",
            )
            self.send_header("Content-Disposition", 'attachment; filename="e2e-fixture.txt"')
        else:
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")

    def log_message(self, *_args) -> None:  # keep console clean
        return None


def serve(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = serve(args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
