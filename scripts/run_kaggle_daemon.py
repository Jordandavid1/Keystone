#!/usr/bin/env python3
"""
KEYSTONE Kaggle Worker Heartbeat Daemon Script
Pumps heartbeats every 30s to the live KEYSTONE Control Plane on http://127.0.0.1:8000.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.harness.src.kaggle_daemon import KaggleWorkerDaemon


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KEYSTONE Kaggle Worker Heartbeat Daemon")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Keystone API base URL")
    parser.add_argument("--interval", type=float, default=30.0, help="Heartbeat pulse interval in seconds")
    parser.add_argument("--oneshot", action="store_true", help="Register and pulse once, then exit")
    args = parser.parse_args()

    daemon = KaggleWorkerDaemon(api_url=args.api_url, heartbeat_interval=args.interval, in_process=False)
    daemon.register_workers_http()
    daemon.pulse_heartbeat()
    print(f"[+] Kaggle T4x2 Cognition & ComfyUI workers registered against {args.api_url}")
    print(f"[+] Initial heartbeat pulsed successfully.")

    if not args.oneshot:
        import time
        print(f"[*] Kaggle worker heartbeat daemon active (pulsing every {args.interval}s)...")
        try:
            while True:
                time.sleep(args.interval)
                daemon.pulse_heartbeat()
        except KeyboardInterrupt:
            print("[*] Kaggle worker daemon stopped.")


if __name__ == "__main__":
    main()
