"""KEYSTONE H3 bridge — authenticated reverse proxy in front of Kaggle ComfyUI.

Runs inside the Kaggle runtime next to ComfyUI (127.0.0.1:8188) and listens on
127.0.0.1:8189. A cloudflared tunnel points at 8189, so every request from the
KEYSTONE API must present ``Authorization: Bearer <token>``.

    python keystone_h3_bridge.py --port 8189 --upstream http://127.0.0.1:8188

Token resolution: ``KEYSTONE_BRIDGE_TOKEN`` (Kaggle Secret / env), otherwise a
random token is generated, written to ``/tmp/keystone_bridge_token`` and printed.
Standard library only.
"""

from __future__ import annotations

import argparse
import http.server
import os
import secrets
import socketserver
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_FILE = Path(tempfile.gettempdir()) / "keystone_bridge_token"
HOP_HEADERS = {"host", "connection", "keep-alive", "proxy-authenticate", "te", "trailers",
               "transfer-encoding", "upgrade", "content-length", "authorization"}


def resolve_token() -> str:
    token = os.getenv("KEYSTONE_BRIDGE_TOKEN", "").strip()
    if token:
        TOKEN_FILE.write_text(token)
        return token
    if TOKEN_FILE.exists():
        existing = TOKEN_FILE.read_text().strip()
        if existing:
            return existing
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token)
    return token


def make_handler(upstream: str, token: str):
    base = upstream.rstrip("/")

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:  # keep Kaggle logs readable
            sys.stderr.write("bridge %s - %s\n" % (self.address_string(), fmt % args))

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            return header.startswith("Bearer ") and secrets.compare_digest(header[7:].strip(), token)

        def _json(self, status: int, payload: bytes, content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _proxy(self) -> None:
            if self.path.split("?")[0] == "/keystone/health":
                body = ('{"ok":true,"upstream":"%s"}' % base).encode()
                return self._json(200, body)

            if not self._authorized():
                return self._json(401, b'{"error":"unauthorized"}')

            length = int(self.headers.get("Content-Length") or 0)
            payload = self.rfile.read(length) if length else None
            headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS}
            headers["Host"] = urllib.parse.urlparse(base).netloc

            request = urllib.request.Request(
                base + self.path, data=payload, headers=headers, method=self.command
            )
            try:
                response = urllib.request.urlopen(request, timeout=1800)
            except urllib.error.HTTPError as exc:
                data = exc.read()
                return self._json(exc.code, data, exc.headers.get("Content-Type", "application/json"))
            except urllib.error.URLError as exc:
                return self._json(502, ('{"error":"upstream unreachable: %s"}' % exc).encode())

            with response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() in {"transfer-encoding", "connection", "content-length"}:
                        continue
                    self.send_header(key, value)
                data = response.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        do_GET = _proxy
        do_POST = _proxy
        do_HEAD = _proxy

    return Handler


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8189)
    parser.add_argument("--upstream", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    token = resolve_token()
    server = ThreadingServer((args.host, args.port), make_handler(args.upstream, token))
    print(f"KEYSTONE H3 bridge on http://{args.host}:{args.port} -> {args.upstream}", flush=True)
    print(f"KEYSTONE_BRIDGE_TOKEN={token}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
