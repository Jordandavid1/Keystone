"""
KEYSTONE Native Windows Desktop Launcher (Option 2)
Bundles KEYSTONE ASGI Backend & Native Desktop Window via pywebview (Edge WebView2).

Invariants Preserved:
- Strict Edge WebView2 integration (aligns with global browser invariant).
- Zero mutation of baseline files.
- Supports --verify flag for headless self-testing and CI validation.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse

# Explicit dynamic driver linking for PyInstaller single-file packaging
import aiosqlite  # noqa: F401
import sqlalchemy.dialects.sqlite.aiosqlite  # noqa: F401
try:
    import passlib.handlers.bcrypt  # noqa: F401
except ImportError:
    pass


def get_base_dir() -> Path:
    """Returns the base runtime directory for both development and PyInstaller frozen modes."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


BASE_DIR = get_base_dir()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from services.cognition.src.client import load_keystone_dotenv
    load_keystone_dotenv()
except Exception:
    pass


def find_free_port(preferred: int = 8000) -> int:
    """Checks if preferred port is available; otherwise finds an ephemeral free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass

    # Preferred was occupied, find another free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


DEFAULT_STUDIO_URL = "http://127.0.0.1:3000"


def resolve_studio_url(cli_url: str | None = None) -> str:
    """Resolves the Next.js Studio URL from CLI, env configuration, or local default."""
    candidate = (
        (cli_url or "").strip()
        or os.getenv("KEYSTONE_STUDIO_URL", "").strip()
        or os.getenv("KEYSTONE_WEB_URL", "").strip()
        or DEFAULT_STUDIO_URL
    )
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid Next.js Studio URL: {candidate!r}")
    return candidate.rstrip("/")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Stops HTTP redirect traversal so /workspace redirect responses can be inspected."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def fetch_no_redirect(url: str, timeout_sec: float = 5.0) -> tuple[int, str | None]:
    """Issues a GET request without following redirects and returns (status, location)."""
    opener = urllib.request.build_opener(_NoRedirectHandler)
    req = urllib.request.Request(url, headers={"User-Agent": "KeystoneDesktop/2.0"})
    try:
        with opener.open(req, timeout=timeout_sec) as resp:
            return resp.status, resp.headers.get("Location")
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("Location")


def is_server_ready(url: str, timeout_sec: float = 1.0) -> bool:
    """Checks if the Keystone server is responding with HTTP 200."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KeystoneDesktop/2.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_for_server(url: str, max_wait_sec: float = 15.0) -> bool:
    """Polls server URL until it responds 200 or times out."""
    start = time.time()
    while time.time() - start < max_wait_sec:
        if is_server_ready(url):
            return True
        time.sleep(0.2)
    return False


def run_uvicorn_server(host: str, port: int, log_level: str = "warning"):
    """Runs Uvicorn in a dedicated daemon thread."""
    import uvicorn
    from apps.api.src.server import app

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(description="KEYSTONE Multimodal Creative Desktop Application")
    parser.add_argument("--port", type=int, default=None, help="Port to bind the internal server to")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument(
        "--studio-url",
        type=str,
        default=None,
        help="Next.js Studio URL to launch (overrides KEYSTONE_STUDIO_URL / KEYSTONE_WEB_URL)",
    )
    parser.add_argument("--verify", action="store_true", help="Run automated self-test and health verification, then exit")
    parser.add_argument("--headless", action="store_true", help="Run the server in foreground without a desktop window")
    args = parser.parse_args()

    port = args.port or find_free_port(8000)
    health_url = f"http://{args.host}:{port}/v1/health"
    workspace_url = f"http://{args.host}:{port}/workspace"
    studio_url = resolve_studio_url(args.studio_url)

    print("=" * 72)
    print("  KEYSTONE CREATIVE STUDIO — NATIVE DESKTOP LAUNCHER")
    print(f"  Target Engine : http://{args.host}:{port}")
    print(f"  Studio UI     : {studio_url}")
    print(f"  Base Runtime  : {BASE_DIR}")
    print("=" * 72)

    # 1. Start server in a background daemon thread
    server_thread = threading.Thread(
        target=run_uvicorn_server,
        args=(args.host, port),
        daemon=True,
        name="KeystoneUvicornThread"
    )
    server_thread.start()

    # 2. Await readiness
    print(f"[*] Waiting for internal server initialization on port {port}...")
    ready = wait_for_server(health_url, max_wait_sec=15.0)
    if not ready:
        print(f"[!] ERROR: Keystone internal server failed to respond on {health_url}")
        sys.exit(1)

    print(f"[+] Keystone server is healthy and responding on port {port}.")

    # 3. If --verify mode, perform full endpoint checks and exit
    if args.verify:
        print("[*] Running automated verification checks...")
        try:
            ws_status, ws_location = fetch_no_redirect(workspace_url, timeout_sec=5.0)
            assert ws_status in (200, 302, 307, 308), f"Unexpected status {ws_status} from /workspace"
            print(f"[+] /workspace verified (HTTP {ws_status}, redirect -> {ws_location or studio_url}).")

            if is_server_ready(studio_url, timeout_sec=2.0):
                req = urllib.request.Request(studio_url, headers={"User-Agent": "KeystoneDesktop/2.0"})
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                    assert resp.status == 200, f"Expected 200 from Studio URL, got {resp.status}"
                    assert "KEYSTONE" in content, "Missing KEYSTONE brand in Studio response"
                    print(f"[+] Next.js Studio verified at {studio_url} ({len(content)} bytes served).")
            else:
                print(f"[i] Next.js Studio not running at {studio_url}; skipping live Next.js HTML check.")

            req_contracts = urllib.request.Request(f"http://{args.host}:{port}/v1/contracts")
            with urllib.request.urlopen(req_contracts, timeout=5.0) as resp:
                contracts_content = resp.read().decode("utf-8")
                assert resp.status == 200, "Expected 200 from /v1/contracts"
                assert "contract_version" in contracts_content
                print("[+] /v1/contracts verified successfully.")

            # Test database connectivity and auth pipeline
            import json
            auth_payload = json.dumps({
                "email": f"verify-{int(time.time())}@keystone.local",
                "password": "VerifyPassword123!",
                "display_name": "Verification User"
            }).encode("utf-8")
            req_auth = urllib.request.Request(
                f"http://{args.host}:{port}/v1/auth/register",
                data=auth_payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_auth, timeout=5.0) as resp:
                assert resp.status in (200, 201), f"Expected 200/201 from /v1/auth/register, got {resp.status}"
                auth_resp = json.loads(resp.read().decode("utf-8"))
                assert "access_token" in auth_resp
                access_token = auth_resp["access_token"]
                print("[+] Database & Auth pipeline verified successfully.")

            # Test Kaggle Worker Bridge (requires service token when configured)
            service_token = (os.getenv("KEYSTONE_INTERNAL_SERVICE_TOKEN") or "").strip()
            worker_headers = {"X-Service-Token": service_token} if service_token else {}
            req_workers = urllib.request.Request(
                f"http://{args.host}:{port}/internal/workers",
                headers=worker_headers,
            )
            try:
                with urllib.request.urlopen(req_workers, timeout=5.0) as resp:
                    workers_data = json.loads(resp.read().decode("utf-8"))
                    assert resp.status == 200, "Expected 200 from /internal/workers"
                    assert "workers" in workers_data
                    print(f"[+] Worker Bridge verified ({workers_data.get('count', 0)} workers registered).")
            except urllib.error.HTTPError as err:
                assert err.code in (401, 403) and not service_token, f"Unexpected /internal/workers error: {err.code}"
                print(f"[+] Worker Bridge auth guard verified (HTTP {err.code} without service token).")

            # Test Remote Config (admin-gated)
            req_remote = urllib.request.Request(
                f"http://{args.host}:{port}/v1/config/remote",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            try:
                with urllib.request.urlopen(req_remote, timeout=5.0) as resp:
                    remote_data = json.loads(resp.read().decode("utf-8"))
                    assert resp.status == 200, "Expected 200 from /v1/config/remote"
                    assert "parameters" in remote_data
                    print("[+] Remote Config verified successfully.")
            except urllib.error.HTTPError as err:
                assert err.code in (401, 403), f"Unexpected /v1/config/remote error: {err.code}"
                print(f"[+] Remote Config admin guard verified (HTTP {err.code} for non-admin user).")

            print("[PASS] Native Desktop Launcher self-verification complete!")

            sys.exit(0)
        except Exception as e:
            print(f"[!] Verification failed: {e}")
            sys.exit(2)

    # 4. If --headless mode, keep main thread alive
    if args.headless:
        print(f"[+] KEYSTONE running in headless mode. API: http://{args.host}:{port} | Studio: {studio_url}. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("[*] Stopping server...")
            sys.exit(0)

    # 5. Native Desktop Window via pywebview (Edge WebView2) pointing at Next.js Studio
    if not is_server_ready(studio_url, timeout_sec=1.0):
        print(
            f"[*] Note: Next.js Studio is not yet responding at {studio_url}. "
            "Start it via 'npm --workspace=apps/web run dev' or set KEYSTONE_STUDIO_URL / KEYSTONE_WEB_URL."
        )
    print(f"[*] Launching native desktop window for {studio_url}...")
    try:
        import webview

        window = webview.create_window(
            title="KEYSTONE Creative Studio — Multimodal Creative Intelligence",
            url=studio_url,
            width=1440,
            height=920,
            min_size=(1024, 720),
            background_color="#06070a"
        )
        # Explicitly use Edge Chromium / WebView2 on Windows
        webview.start(gui="edgechromium", debug=False)
        print("[*] Native desktop window closed. Exiting.")
    except Exception as e:
        print(f"[!] Failed to launch pywebview desktop window: {e}")
        print(f"[*] Falling back to default browser at {studio_url}")
        import webbrowser
        webbrowser.open(studio_url)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
