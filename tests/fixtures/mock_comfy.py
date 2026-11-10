"""ComfyUI-compatible mock used to verify the H3 adapter without Kaggle.

Serves real ComfyUI endpoint shapes:
  GET  /system_stats, /history/{id}, /view
  POST /upload/image, /prompt

The adapter's queued workflow is validated here: the prompt must be filled, the
first reference must reference an uploaded image, and a second reference must be
either connected to an uploaded image or explicitly disconnected.
"""

import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / ".run" / "sample.mp4"
UPLOADS: set = set()
PROMPTS = {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("mock %s\n" % (fmt % args))

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/system_stats":
            return self._json(200, {"system": {"os": "mock"}, "devices": [{"name": "Tesla T4"}]})
        if path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            if prompt_id not in PROMPTS:
                return self._json(200, {})
            return self._json(200, {prompt_id: {
                "status": {"status_str": "success", "completed": True},
                "outputs": {"148": {"gifs": [{"filename": VIDEO.name, "subfolder": "", "type": "output"}]}},
            }})
        if path == "/view":
            data = VIDEO.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if path == "/upload/image":
            name = f"upload-{uuid.uuid4().hex[:8]}.png"
            UPLOADS.add(name)
            return self._json(200, {"name": name, "subfolder": "", "type": "input"})
        if path == "/prompt":
            workflow = (json.loads(body or b"{}") or {}).get("prompt") or {}
            text = ((workflow.get("138") or {}).get("inputs") or {}).get("value", "")
            first = ((workflow.get("181") or {}).get("inputs") or {}).get("image", "")
            second = ((workflow.get("187") or {}).get("inputs") or {}).get("image")
            second_linked = "ref_images.ref_image_1" in ((workflow.get("136") or {}).get("inputs") or {})
            if not text or first not in UPLOADS:
                return self._json(400, {"error": "prompt or primary reference missing"})
            if second_linked and second not in UPLOADS:
                return self._json(400, {"error": f"secondary reference invalid: {second!r}"})
            prompt_id = str(uuid.uuid4())
            PROMPTS[prompt_id] = {
                "nodes": len(workflow),
                "text": text,
                "first": first,
                "second": second if second_linked else None,
                "duration": ((workflow.get("132") or {}).get("inputs") or {}).get("value"),
                "steps": ((workflow.get("143") or {}).get("inputs") or {}).get("value"),
            }
            print("queued", json.dumps(PROMPTS[prompt_id]), flush=True)
            return self._json(200, {"prompt_id": prompt_id, "number": 1})
        return self._json(404, {"error": "not found"})


if __name__ == "__main__":
    if not VIDEO.exists():
        raise SystemExit(f"missing fixture video: {VIDEO}")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8199
    print(f"mock comfy {port}, video {VIDEO.stat().st_size} bytes", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
