#!/usr/bin/env python3
"""
KEYSTONE Kaggle Worker Registration & CLI Push Utility (Bible §24)

Supports two workflows:
1. Direct tunnel registration against your running KEYSTONE Control Plane:
   .venv\\Scripts\\python KAGGLE_SETUP/scripts/setup_kaggle.py --register-tunnel https://your-tunnel.trycloudflare.com

2. Automated Kaggle API Kernel Push (when KAGGLE_USERNAME & KAGGLE_KEY or ~/.kaggle/kaggle.json are set):
   .venv\\Scripts\\python KAGGLE_SETUP/scripts/setup_kaggle.py --push-kernels --kaggle-user <username>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict

PINNED_CHECKPOINT = "huihui-ai/Huihui-Qwen3.8-27B-abliterated"
REPO_ROOT = Path(__file__).resolve().parents[2]
KAGGLE_SETUP_DIR = REPO_ROOT / "KAGGLE_SETUP"


def register_ephemeral_tunnel(
    api_url: str,
    cognition_tunnel_url: str,
    creative_tunnel_url: str = "",
    worker_id: str = "kaggle_worker_t4x2_01"
) -> Dict[str, Any]:
    """
    Registers a live Kaggle tunnel URL with the KEYSTONE Control Plane (/internal/workers/register).
    Once registered, CognitionConnector and ProviderRouter automatically route to this URL.
    """
    api_base = api_url.rstrip("/")
    payload = {
        "worker_id": worker_id,
        "worker_type": "cognition",
        "tunnel_url": cognition_tunnel_url.rstrip("/"),
        "capabilities": [
            "cognition.qwen27b",
            "cognition.reasoning",
            "image.generation",
            "image.editing",
            "video.i2v",
            "video.t2v",
            "identity.face_swap",
            "image.upscale"
        ],
        "hardware": {
            "gpus": 2,
            "gpu_model": "NVIDIA Tesla T4",
            "vram_total_gib": 30.0,
            "host_ram_gib": 80.0,
            "cognition_checkpoint": PINNED_CHECKPOINT,
            "creative_tunnel_url": (creative_tunnel_url or cognition_tunnel_url).rstrip("/")
        }
    }

    req = urllib.request.Request(
        f"{api_base}/internal/workers/register",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate_kernel_metadata(kaggle_username: str, notebook_name: str, slug: str, title: str) -> Dict[str, Any]:
    """Generates Kaggle CLI kernel-metadata.json configured for 2x T4 GPU and Internet access."""
    return {
        "id": f"{kaggle_username}/{slug}",
        "title": title,
        "code_file": notebook_name,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": "true",
        "enable_gpu": "true",
        "enable_tpu": "false",
        "enable_internet": "true",
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": []
    }


def push_kaggle_kernels(kaggle_username: str) -> None:
    """Packages and pushes the 3 KEYSTONE notebooks to Kaggle via `kaggle kernels push`."""
    kernels = [
        (
            "01_keystone_cognition_bootstrap.ipynb",
            "keystone-cognition-bootstrap",
            "KEYSTONE 01 Cognition Bootstrap (Qwen 3.8 27B T4x2)"
        ),
        (
            "02_keystone_comfyui_runtime.ipynb",
            "keystone-comfyui-runtime",
            "KEYSTONE 02 ComfyUI & Creative Tool Fabric Runtime"
        ),
        (
            "03_keystone_integrated_gateway.ipynb",
            "keystone-integrated-gateway",
            "KEYSTONE 03 Integrated Gateway & Tunnel Bridge"
        )
    ]

    build_dir = KAGGLE_SETUP_DIR / "logs" / "kernel_push_staging"
    build_dir.mkdir(parents=True, exist_ok=True)

    for nb_file, slug, title in kernels:
        stage_subdir = build_dir / slug
        stage_subdir.mkdir(parents=True, exist_ok=True)

        src_nb = KAGGLE_SETUP_DIR / "notebooks" / nb_file
        dst_nb = stage_subdir / nb_file
        dst_nb.write_bytes(src_nb.read_bytes())

        meta = generate_kernel_metadata(kaggle_username, nb_file, slug, title)
        meta_path = stage_subdir / "kernel-metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"[Prepared] {meta['id']} -> {meta_path}")

        try:
            res = subprocess.run(
                ["kaggle", "kernels", "push", "-p", str(stage_subdir)],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                print(f"[Pushed] {meta['id']}: {res.stdout.strip()}")
            else:
                print(f"[Notice] kaggle CLI returned {res.returncode}: {res.stderr.strip() or res.stdout.strip()}")
        except FileNotFoundError:
            print("[Notice] `kaggle` CLI not installed in PATH. Staging metadata generated ready for push.")


def main() -> int:
    parser = argparse.ArgumentParser(description="KEYSTONE Kaggle Setup & Tunnel Registration Utility")
    parser.add_argument(
        "--api-url",
        default=os.getenv("KEYSTONE_API_URL", "http://localhost:8000"),
        help="KEYSTONE Control Plane URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--register-tunnel",
        default="",
        help="Ephemeral Cloudflare/ngrok tunnel URL from Kaggle to register with KEYSTONE"
    )
    parser.add_argument(
        "--creative-tunnel",
        default="",
        help="Optional separate creative harness tunnel URL (defaults to --register-tunnel)"
    )
    parser.add_argument(
        "--push-kernels",
        action="store_true",
        help="Generate kernel-metadata.json and push the 3 notebooks via Kaggle API"
    )
    parser.add_argument(
        "--kaggle-user",
        default=os.getenv("KAGGLE_USERNAME", "keystone-operator"),
        help="Kaggle username for kernel-metadata.json"
    )

    args = parser.parse_args()

    if args.register_tunnel:
        result = register_ephemeral_tunnel(
            api_url=args.api_url,
            cognition_tunnel_url=args.register_tunnel,
            creative_tunnel_url=args.creative_tunnel
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.push_kernels:
        push_kaggle_kernels(args.kaggle_user)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
