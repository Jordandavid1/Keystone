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
    parser.add_argument("--verify", action="store_true", help="Run automated self-test and health verification, then exit")
    parser.add_argument("--headless", action="store_true", help="Run the server in foreground without a desktop window")
    args = parser.parse_args()

    port = args.port or find_free_port(8000)
    health_url = f"http://{args.host}:{port}/v1/health"
    workspace_url = f"http://{args.host}:{port}/workspace"

    print("=" * 72)
    print("  KEYSTONE CREATIVE STUDIO — NATIVE DESKTOP LAUNCHER")
    print(f"  Target Engine : http://{args.host}:{port}")
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
            req = urllib.request.Request(workspace_url)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                content = resp.read().decode("utf-8")
                assert resp.status == 200, f"Expected 200 from /workspace, got {resp.status}"
                assert "region-topbar" in content, "Missing region-topbar in /workspace response"
                assert "region-canvas" in content, "Missing region-canvas in /workspace response"
                assert "KEYSTONE" in content, "Missing KEYSTONE brand in /workspace response"
                print(f"[+] /workspace verified successfully ({len(content)} bytes served).")

            req_contracts = urllib.request.Request(f"http://{args.host}:{port}/v1/contracts")
            with urllib.request.urlopen(req_contracts, timeout=5.0) as resp:
                contracts_content = resp.read().decode("utf-8")
                assert resp.status == 200, "Expected 200 from /v1/contracts"
                assert "contract_version" in contracts_content
                print("[+] /v1/contracts verified successfully.")

            # Test database connectivity and aiosqlite driver
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
                print("[+] Async Database (aiosqlite) & Auth pipeline verified successfully.")

            # Test Kaggle Worker Bridge
            req_workers = urllib.request.Request(f"http://{args.host}:{port}/internal/workers")
            with urllib.request.urlopen(req_workers, timeout=5.0) as resp:
                workers_data = json.loads(resp.read().decode("utf-8"))
                assert resp.status == 200, "Expected 200 from /internal/workers"
                assert "workers" in workers_data
                assert workers_data.get("count", 0) >= 2, f"Expected at least 2 active workers, got {workers_data.get('count', 0)}"
                print(f"[+] Kaggle Worker Bridge verified successfully ({workers_data.get('count', 0)} workers active).")

            # Test Remote Config
            req_remote = urllib.request.Request(f"http://{args.host}:{port}/v1/config/remote")
            with urllib.request.urlopen(req_remote, timeout=5.0) as resp:
                remote_data = json.loads(resp.read().decode("utf-8"))
                assert resp.status == 200, "Expected 200 from /v1/config/remote"
                assert "parameters" in remote_data
                print("[+] Remote Config verified successfully.")

            print("[PASS] Native Desktop Launcher self-verification complete!")

            sys.exit(0)
        except Exception as e:
            print(f"[!] Verification failed: {e}")
            sys.exit(2)

    # 4. If --headless mode, keep main thread alive
    if args.headless:
        print(f"[+] KEYSTONE running in headless mode at {workspace_url}. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("[*] Stopping server...")
            sys.exit(0)

    # 5. Native Desktop Window via pywebview (Edge WebView2)
    print(f"[*] Launching native desktop window for {workspace_url}...")
    try:
        import webview

        window = webview.create_window(
            title="KEYSTONE Creative Studio — Multimodal Creative Intelligence",
            url=workspace_url,
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
        print(f"[*] Falling back to default browser at {workspace_url}")
        import webbrowser
        webbrowser.open(workspace_url)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
