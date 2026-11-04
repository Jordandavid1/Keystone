"""
Build script for KEYSTONE Native Windows Desktop Executable (Option 2).
Uses PyInstaller to bundle the FastAPI backend, pywebview (Edge WebView2),
and the 5-Region Hollywood UX into dist/keystone-desktop.exe.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def build():
    print("=" * 72)
    print("  KEYSTONE DESKTOP EXECUTABLE PACKAGER (PyInstaller)")
    print(f"  Repo Root : {REPO_ROOT}")
    print("=" * 72)

    pyinstaller_exe = REPO_ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    if not pyinstaller_exe.exists():
        pyinstaller_exe = "pyinstaller"

    launcher_path = REPO_ROOT / "apps" / "desktop" / "launcher.py"
    if not launcher_path.exists():
        raise FileNotFoundError(f"Launcher not found at {launcher_path}")

    # Separator for Windows data bundling is ';'
    add_data_args = [
        f"--add-data={REPO_ROOT / 'apps' / 'web'};apps/web",
        f"--add-data={REPO_ROOT / 'apps' / 'admin'};apps/admin",
        f"--add-data={REPO_ROOT / 'packages'};packages",
        f"--add-data={REPO_ROOT / 'services'};services",
        f"--add-data={REPO_ROOT / 'remote_config.json'};.",
    ]


    collect_all_args = [
        "--collect-all=aiosqlite",
        "--collect-all=sqlalchemy",
        "--collect-all=passlib",
        "--collect-all=bcrypt",
    ]

    hidden_imports = [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "fastapi",
        "pydantic",
        "pydantic_core",
        "sqlite3",
        "aiosqlite",
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "greenlet",
        "passlib",
        "passlib.handlers.bcrypt",
        "bcrypt",
        "email_validator",
        "webview",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ]

    hidden_args = [f"--hidden-import={mod}" for mod in hidden_imports]

    cmd = [
        str(pyinstaller_exe),
        "--noconfirm",
        "--clean",
        "--name=keystone-desktop",
        "--onefile",
        *add_data_args,
        *collect_all_args,
        *hidden_args,
        f"--paths={REPO_ROOT}",
        str(launcher_path)
    ]

    print("[*] Running PyInstaller build command:")
    print(" ".join(cmd[:8]) + " ... [data & hidden imports omitted for brevity]")

    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(f"[!] PyInstaller build failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    dist_exe = REPO_ROOT / "dist" / "keystone-desktop.exe"
    if not dist_exe.exists():
        print(f"[!] ERROR: Expected binary not found at {dist_exe}")
        sys.exit(1)

    exe_size_mb = dist_exe.stat().st_size / (1024 * 1024)
    print("=" * 72)
    print(f"[SUCCESS] Native Windows Executable Built Successfully!")
    print(f"  Artifact Path : {dist_exe}")
    print(f"  Binary Size   : {exe_size_mb:.2f} MB")
    print("=" * 72)


if __name__ == "__main__":
    build()
