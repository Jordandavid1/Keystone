"""
KEYSTONE Live ComfyUI & Cognition Runtime Manager.

Provides real process discovery, local ComfyUI daemon launch/stop with automatic
CUDA vs CPU detection, live /system_stats probing, MiniMax-H3 workflow readiness,
and dynamic endpoint wiring for both local ComfyUI and remote GPU workers
(RunPod, Together.ai, Fireworks.ai, Hugging Face, Colab).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_RUNTIME_LOCK = threading.Lock()
_MANAGED_COMFY_PROC: Optional[subprocess.Popen] = None
_LAST_BOOT_ERROR: Optional[str] = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def discover_local_comfy_dir() -> Optional[Path]:
    """Locate a local ComfyUI installation directory if present on the host."""
    candidates: List[Path] = []
    env_home = os.getenv("COMFYUI_HOME", "").strip()
    if env_home:
        candidates.append(Path(env_home))
    candidates.extend(
        [
            Path.home() / "ComfyUI",
            _repo_root().parent / "ComfyUI",
            Path("C:/ComfyUI"),
            Path("/opt/ComfyUI"),
        ]
    )
    for cand in candidates:
        try:
            if cand.is_dir() and (cand / "main.py").is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def resolve_comfy_python(comfy_dir: Path) -> str:
    """Resolve the Python interpreter inside ComfyUI's virtual environment."""
    win_py = comfy_dir / "venv" / "Scripts" / "python.exe"
    if win_py.is_file():
        return str(win_py)
    posix_py = comfy_dir / "venv" / "bin" / "python"
    if posix_py.is_file():
        return str(posix_py)
    win_dotvenv = comfy_dir / ".venv" / "Scripts" / "python.exe"
    if win_dotvenv.is_file():
        return str(win_dotvenv)
    return sys.executable


def detect_torch_cuda(python_exe: str) -> bool:
    """Return True only when the target interpreter has CUDA compiled and an active GPU."""
    try:
        proc = subprocess.run(
            [python_exe, "-c", "import torch; print('1' if torch.cuda.is_available() else '0')"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        return proc.returncode == 0 and proc.stdout.strip().endswith("1")
    except Exception:
        return False


def probe_comfy_endpoint(base_url: str, api_key: str = "", timeout: float = 3.0) -> Dict[str, Any]:
    """Probe a ComfyUI server via GET /system_stats and return live hardware telemetry."""
    clean = (base_url or "").strip().rstrip("/")
    if not clean:
        return {"reachable": False, "url": None, "system_stats": None, "error": "No ComfyUI URL set"}
    headers = {"User-Agent": "KEYSTONE-RuntimeManager/2.0"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    req = urllib.request.Request(f"{clean}/system_stats", headers=headers, method="GET")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            return {
                "reachable": resp.status == 200,
                "url": clean,
                "latency_ms": latency_ms,
                "system_stats": body,
                "error": None,
            }
    except Exception as exc:
        return {
            "reachable": False,
            "url": clean,
            "latency_ms": None,
            "system_stats": None,
            "error": str(exc),
        }


def validate_studio_endpoint_url(url: str, field_name: str) -> str:
    """Validate an operator-supplied runtime URL, blocking CRLF injection and cloud metadata SSRF."""
    if "\r" in url or "\n" in url:
        raise ValueError(f"INVALID_INPUT: Newline characters are forbidden in {field_name}")
    clean = url.strip().rstrip("/")
    if not clean:
        return ""
    parsed = urllib.parse.urlparse(clean)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"INVALID_URL: {field_name} must be a valid http:// or https:// URL")
    host = parsed.hostname.lower()
    if host in ("169.254.169.254", "metadata.google.internal", "metadata"):
        raise ValueError("SSRF_BLOCKED: Cloud metadata endpoints are forbidden")
    return clean


def _persist_env_updates(updates: Dict[str, str]) -> None:
    if not updates or "pytest" in sys.modules:
        return
    root = _repo_root()
    for env_path in (root / ".env", root / "dist" / ".env"):
        if not env_path.parent.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
            written = set()
            out_lines: List[str] = []
            for line in lines:
                stripped = line.strip()
                if "=" in stripped and not stripped.startswith("#"):
                    k = stripped.split("=", 1)[0].strip()
                    if k in updates:
                        out_lines.append(f"{k}={updates[k]}")
                        written.add(k)
                        continue
                out_lines.append(line)
            for k, v in updates.items():
                if k not in written:
                    out_lines.append(f"{k}={v}")
            env_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        except OSError:
            continue


def register_comfy_in_worker_bridge(clean_url: str, system_stats: Optional[Dict[str, Any]] = None) -> None:
    """Register the active ComfyUI runtime with full creative & MiniMax-H3 capabilities."""
    if not clean_url:
        return
    from services.harness.src.worker_bridge import worker_bridge

    devices = (system_stats or {}).get("devices") or []
    dev0 = devices[0] if devices else {}
    gpu_name = str(dev0.get("name") or dev0.get("type") or "ComfyUI Runtime")
    vram_bytes = float(dev0.get("vram_total") or 0.0)
    vram_gib = round(vram_bytes / (1024.0 ** 3), 2) if vram_bytes > 0 else 16.0

    worker_bridge.register_worker(
        worker_id="keystone-comfyui-primary",
        worker_type="creative_worker",
        tunnel_url=clean_url,
        capabilities=[
            "creative.comfyui",
            "image.generation",
            "image.editing",
            "video.i2v",
            "video.t2v",
            "video.minimax_h3_ref2va",
            "identity.facefusion",
            "upscale.clarity",
        ],
        hardware={"gpu": gpu_name, "vram_total_gib": vram_gib},
    )


def configure_studio_runtime(
    *,
    comfy_base_url: Optional[str] = None,
    comfy_api_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    openai_model: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Apply live ComfyUI and Cognition runtime settings to environment, WorkerBridge, and .env."""
    from services.harness.src.worker_bridge import worker_bridge

    updates: Dict[str, str] = {}

    if comfy_base_url is not None:
        clean_comfy = validate_studio_endpoint_url(comfy_base_url, "comfy_base_url")
        if clean_comfy.endswith("/v1"):
            clean_comfy = clean_comfy[:-3].rstrip("/")
        os.environ["COMFY_BASE_URL"] = clean_comfy
        os.environ["KEYSTONE_COMFY_URL"] = clean_comfy
        os.environ["KAGGLE_COMFYUI_TUNNEL"] = clean_comfy
        updates["COMFY_BASE_URL"] = clean_comfy
        updates["KEYSTONE_COMFY_URL"] = clean_comfy
        if clean_comfy:
            probe = probe_comfy_endpoint(clean_comfy, api_key=comfy_api_key or os.getenv("KEYSTONE_COMFY_API_KEY", ""))
            register_comfy_in_worker_bridge(clean_comfy, probe.get("system_stats"))

    if comfy_api_key is not None:
        if "\r" in comfy_api_key or "\n" in comfy_api_key:
            raise ValueError("INVALID_INPUT: Newline characters are forbidden in comfy_api_key")
        clean_ckey = comfy_api_key.strip()
        os.environ["KEYSTONE_COMFY_API_KEY"] = clean_ckey
        os.environ["COMFY_BEARER_TOKEN"] = clean_ckey
        updates["KEYSTONE_COMFY_API_KEY"] = clean_ckey

    if openai_base_url is not None:
        clean_oai = validate_studio_endpoint_url(openai_base_url, "openai_base_url")
        if clean_oai and not clean_oai.endswith("/v1"):
            clean_oai = f"{clean_oai}/v1"
        os.environ["OPENAI_BASE_URL"] = clean_oai
        os.environ["COGNITION_BASE_URL"] = clean_oai
        updates["OPENAI_BASE_URL"] = clean_oai
        updates["COGNITION_BASE_URL"] = clean_oai
        if clean_oai:
            worker_bridge.register_worker(
                worker_id="keystone-cognition-primary",
                worker_type="cognition_worker",
                tunnel_url=clean_oai,
                capabilities=["cognition.qwen_27b", "cognition.reasoning", "planning.propose"],
                hardware={"gpu": "Open-Weight Inference Runtime", "vram_total_gib": 80.0},
            )

    if openai_api_key is not None:
        if "\r" in openai_api_key or "\n" in openai_api_key:
            raise ValueError("INVALID_INPUT: Newline characters are forbidden in openai_api_key")
        clean_okey = openai_api_key.strip()
        os.environ["OPENAI_API_KEY"] = clean_okey
        updates["OPENAI_API_KEY"] = clean_okey

    if openai_model is not None and openai_model.strip():
        if "\r" in openai_model or "\n" in openai_model:
            raise ValueError("INVALID_INPUT: Newline characters are forbidden in openai_model")
        clean_model = openai_model.strip()
        os.environ["OPENAI_MODEL"] = clean_model
        updates["OPENAI_MODEL"] = clean_model

    if persist and updates:
        _persist_env_updates(updates)

    return updates


def launch_local_comfy_daemon(
    host: str = "127.0.0.1",
    port: int = 8188,
    wait_seconds: float = 45.0,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Ensure local ComfyUI is running on http://{host}:{port}, spawning it if needed,
    and bind it immediately into KEYSTONE runtime configuration and WorkerBridge.
    """
    global _MANAGED_COMFY_PROC, _LAST_BOOT_ERROR

    target_url = f"http://{host}:{port}"
    initial_probe = probe_comfy_endpoint(target_url, timeout=2.0)
    if initial_probe["reachable"]:
        configure_studio_runtime(comfy_base_url=target_url, persist=True)
        _LAST_BOOT_ERROR = None
        return True, f"Connected to active ComfyUI server at {target_url}", initial_probe

    comfy_dir = discover_local_comfy_dir()
    if comfy_dir is None:
        _LAST_BOOT_ERROR = "Local ComfyUI directory not found (checked COMFYUI_HOME and ~/ComfyUI)."
        return False, _LAST_BOOT_ERROR, initial_probe

    with _RUNTIME_LOCK:
        recheck = probe_comfy_endpoint(target_url, timeout=1.5)
        if recheck["reachable"]:
            configure_studio_runtime(comfy_base_url=target_url, persist=True)
            _LAST_BOOT_ERROR = None
            return True, f"Connected to active ComfyUI server at {target_url}", recheck

        py_exe = resolve_comfy_python(comfy_dir)
        has_cuda = detect_torch_cuda(py_exe)
        cmd = [py_exe, "main.py", "--listen", host, "--port", str(port)]
        if not has_cuda:
            cmd.append("--cpu")

        log_dir = _repo_root() / ".run"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = open(log_dir / "comfyui_daemon.log", "a", encoding="utf-8")

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(comfy_dir),
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            )
        else:
            popen_kwargs["start_new_session"] = True

        try:
            _MANAGED_COMFY_PROC = subprocess.Popen(cmd, **popen_kwargs)
        except Exception as exc:
            _LAST_BOOT_ERROR = f"Failed to start ComfyUI process: {exc}"
            return False, _LAST_BOOT_ERROR, initial_probe

    deadline = time.time() + max(5.0, float(wait_seconds))
    last_probe = initial_probe
    while time.time() < deadline:
        if _MANAGED_COMFY_PROC is not None and _MANAGED_COMFY_PROC.poll() is not None:
            _LAST_BOOT_ERROR = f"ComfyUI exited early with code {_MANAGED_COMFY_PROC.returncode}. Check .run/comfyui_daemon.log."
            return False, _LAST_BOOT_ERROR, last_probe
        last_probe = probe_comfy_endpoint(target_url, timeout=2.0)
        if last_probe["reachable"]:
            configure_studio_runtime(comfy_base_url=target_url, persist=True)
            _LAST_BOOT_ERROR = None
            mode_label = "CUDA GPU" if has_cuda else "CPU"
            return True, f"ComfyUI launched ({mode_label}) and wired at {target_url}", last_probe
        time.sleep(1.0)

    _LAST_BOOT_ERROR = f"ComfyUI is still loading after {int(wait_seconds)}s (check .run/comfyui_daemon.log)."
    return False, _LAST_BOOT_ERROR, last_probe


def stop_local_comfy_daemon() -> Tuple[bool, str]:
    """Stop the managed local ComfyUI subprocess if running."""
    global _MANAGED_COMFY_PROC
    with _RUNTIME_LOCK:
        if _MANAGED_COMFY_PROC is None or _MANAGED_COMFY_PROC.poll() is not None:
            _MANAGED_COMFY_PROC = None
            return False, "No managed ComfyUI subprocess is currently tracked by this API worker."
        try:
            _MANAGED_COMFY_PROC.terminate()
            _MANAGED_COMFY_PROC.wait(timeout=8)
        except Exception:
            try:
                _MANAGED_COMFY_PROC.kill()
            except Exception:
                pass
        _MANAGED_COMFY_PROC = None
        return True, "Managed local ComfyUI process stopped."


def get_last_boot_error() -> Optional[str]:
    return _LAST_BOOT_ERROR


def auto_bootstrap_comfy_background() -> None:
    """
    Auto-wire or auto-launch ComfyUI in a daemon thread when the KEYSTONE API server starts.
    Skipped automatically inside pytest runs or when KEYSTONE_DISABLE_AUTO_COMFY=1.
    """
    if "pytest" in sys.modules or os.getenv("KEYSTONE_DISABLE_AUTO_COMFY", "0") == "1":
        return

    def _worker() -> None:
        try:
            configured_url = (
                os.getenv("COMFY_BASE_URL", "").strip()
                or os.getenv("KEYSTONE_COMFY_URL", "").strip()
            )
            if configured_url:
                probe = probe_comfy_endpoint(configured_url, timeout=3.0)
                if probe["reachable"]:
                    register_comfy_in_worker_bridge(configured_url, probe.get("system_stats"))
                    return
            # Check local 8188 or auto-launch local ComfyUI installation
            local_probe = probe_comfy_endpoint("http://127.0.0.1:8188", timeout=2.0)
            if local_probe["reachable"]:
                configure_studio_runtime(comfy_base_url="http://127.0.0.1:8188", persist=True)
                return
            if discover_local_comfy_dir() is not None:
                launch_local_comfy_daemon(host="127.0.0.1", port=8188, wait_seconds=75.0)
        except Exception:
            pass

    t = threading.Thread(target=_worker, name="keystone-comfy-autoboot", daemon=True)
    t.start()
