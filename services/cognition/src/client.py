"""
KEYSTONE Cognition Client & vLLM Connector (Python Implementation)
Implements client interface to the locked abliterated cognition checkpoint
(OBLITERATUS/Qwen3.8-27B-OBLITERATED) running on Modal A100 / Kaggle 2x NVIDIA T4.
Enforces invariant checkpoint pinning, prohibits model substitution, validates structured
ProposedAction JSON output, and collects latency and token usage telemetry
per Bible §2 Invariant 6, 10, §10, §11, §24, §37 (ADR-003).
"""

from __future__ import annotations
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union
import httpx

from pathlib import Path
import sys
from packages.contracts.src.models import ProposedAction, PromptIntent, CognitiveResult

PINNED_CHECKPOINT = "OBLITERATUS/Qwen3.8-27B-OBLITERATED"
ALLOWED_SERVED_ALIASES = {
    PINNED_CHECKPOINT,
    f"{PINNED_CHECKPOINT}:fastest",
    "obliteratus-qwen3.8-v3",
    "obliteratus-qwen3.8-27b-obliterated",
}


_DOTENV_MTIMES: Dict[str, float] = {}


def load_keystone_dotenv() -> None:
    """Loads .env from executable folder (dist/), current working directory, and repo root."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    candidates.extend([
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[3] / "dist" / ".env",
    ])
    for env_path in candidates:
        try:
            if not env_path.is_file():
                continue
            key_path = str(env_path.resolve())
            mtime = env_path.stat().st_mtime
            prev_mtime = _DOTENV_MTIMES.get(key_path)
            file_changed = prev_mtime is not None and mtime > prev_mtime
            _DOTENV_MTIMES[key_path] = mtime
            for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (k not in os.environ or file_changed):
                    os.environ[k] = v
        except Exception:
            pass


load_keystone_dotenv()


class CognitionConnector:
    """
    Cognition Connector and vLLM client adapter.
    Interface for cognitive reasoning and plan proposal generation.
    Strictly pinned to OBLITERATUS/Qwen3.8-27B-OBLITERATED.
    """

    PINNED_CHECKPOINT = PINNED_CHECKPOINT

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        load_keystone_dotenv()
        self._explicit_base_url = base_url.rstrip("/") if base_url else None
        env_base = (
            os.getenv("COGNITION_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
        )
        self.base_url = (self._explicit_base_url or env_base).rstrip("/")
        self.api_key = (
            api_key
            or os.getenv("COGNITION_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )

    def resolve_api_key(self) -> str:
        load_keystone_dotenv()
        return (
            self.api_key
            or os.getenv("COGNITION_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )

    def resolve_served_model(self) -> str:
        load_keystone_dotenv()
        env_model = os.getenv("OPENAI_MODEL", "").strip()
        if env_model and env_model in ALLOWED_SERVED_ALIASES:
            return env_model
        return self.PINNED_CHECKPOINT

    def resolve_active_endpoint(self) -> str:
        """
        Dynamically resolves the live vLLM endpoint URL in priority order:
        1. Explicit constructor base_url (if passed by caller)
        2. Active ephemeral Kaggle/Colab worker registered in WorkerBridge
        3. COGNITION_BASE_URL or OPENAI_BASE_URL environment variable
        Returns empty string when no cognition engine is configured.
        """
        load_keystone_dotenv()
        if self._explicit_base_url:
            return self._explicit_base_url

        env_url = (
            os.getenv("COGNITION_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
        ).rstrip("/")
        if env_url and not env_url.endswith("/v1"):
            env_url = f"{env_url}/v1"

        try:
            from services.harness.src.worker_bridge import worker_bridge
            cognition_caps = (
                "cognition.qwen27b",
                "cognition.reasoning",
                "cognition",
                PINNED_CHECKPOINT
            )
            for cap in cognition_caps:
                matched = worker_bridge.route_for_capability(cap)
                if matched:
                    tunnel = matched[0].tunnel_url.rstrip("/")
                    if tunnel:
                        return tunnel if tunnel.endswith("/v1") else f"{tunnel}/v1"

            for worker in worker_bridge.list_workers(active_only=True):
                w_type = str(worker.get("worker_type", "")).lower()
                if any(k in w_type for k in ("cognition", "vllm", "qwen", "gateway")):
                    tunnel = str(worker.get("tunnel_url", "")).rstrip("/")
                    if tunnel:
                        return tunnel if tunnel.endswith("/v1") else f"{tunnel}/v1"
        except Exception:
            pass

        return env_url or ""

    @classmethod
    def build_completion_request(
        cls,
        prompt: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Builds OpenAI-compatible chat completion payload.
        Enforces empty prompt rejection and strictly prohibits checkpoint mutation.
        """
        if prompt is None or not str(prompt).strip():
            raise ValueError("EMPTY_PROMPT: Prompt is required")

        opts = options or {}
        requested_model = opts.get("model", cls.PINNED_CHECKPOINT)

        if requested_model != cls.PINNED_CHECKPOINT:
            raise ValueError(
                f"PROHIBITED_CHECKPOINT_MUTATION: Only pinned checkpoint '{cls.PINNED_CHECKPOINT}' is permitted"
            )

        temperature = opts.get("temperature", 0.2)
        max_tokens = opts.get("max_tokens", 2048)

        return {
            "model": cls.PINNED_CHECKPOINT,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are KEYSTONE embedded cognition. Output only structured JSON ProposedAction "
                        "with fields: action_type, capability, parameters, rationale, estimated_credits."
                    )
                },
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

    @classmethod
    def parse_response(
        cls,
        raw_response: Optional[Dict[str, Any]],
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses vLLM completion response, generating unique reasoning_id, extracting ProposedAction,
        and collecting real token usage and latency telemetry.
        """
        reasoning_id = f"reas_{uuid.uuid4().hex[:8]}"

        if not raw_response:
            return {
                "reasoning_id": reasoning_id,
                "model": cls.PINNED_CHECKPOINT,
                "proposed_action": None,
                "raw_text": "",
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                },
                "latency_ms": 0
            }

        choices = raw_response.get("choices")
        proposed_action: Optional[ProposedAction] = None
        raw_text: str = ""

        if choices and isinstance(choices, list) and len(choices) > 0:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                msg = first_choice.get("message")
                if isinstance(msg, dict):
                    raw_text = msg.get("content", "")
                elif "text" in first_choice:
                    raw_text = first_choice.get("text", "")

            if raw_text:
                clean_text = raw_text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_text = "\n".join(lines).strip()

                try:
                    action_data = json.loads(clean_text)
                    proposed_action = cls.validate_proposed_action(action_data)
                except Exception as e:
                    raise ValueError(f"INVALID_PROPOSED_ACTION: Failed to parse structured action: {e}")

        # Extract usage telemetry
        usage = raw_response.get("usage")
        if usage and isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
        else:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

        # If token counts missing from API, compute realistically from prompt and output text
        if prompt_tokens is None:
            prompt_tokens = max(1, len(prompt.split())) if prompt else (max(1, len(raw_text.split())) if raw_text else 0)

        if completion_tokens is None:
            completion_tokens = max(1, len(raw_text.split())) if raw_text else 0

        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        latency_ms = raw_response.get("latency_ms", 0)

        return {
            "reasoning_id": reasoning_id,
            "model": cls.PINNED_CHECKPOINT,
            "proposed_action": proposed_action,
            "raw_text": raw_text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            "latency_ms": latency_ms
        }

    @classmethod
    def validate_proposed_action(cls, action_data: Union[Dict[str, Any], ProposedAction]) -> ProposedAction:
        """Validates that a dictionary conforms to the canonical ProposedAction Pydantic schema."""
        if isinstance(action_data, ProposedAction):
            return action_data
        if not isinstance(action_data, dict):
            raise ValueError("INVALID_PROPOSED_ACTION: Action data must be a dictionary")
        # Ensure mandatory fields for cognition output are present and valid
        if "action_type" not in action_data or not str(action_data["action_type"]).strip():
            raise ValueError("INVALID_PROPOSED_ACTION: action_type is required")
        if "capability" not in action_data or not str(action_data["capability"]).strip():
            raise ValueError("INVALID_PROPOSED_ACTION: capability is required")
        if "parameters" in action_data and not isinstance(action_data["parameters"], dict):
            raise ValueError("INVALID_PROPOSED_ACTION: parameters must be a dictionary")
        if "rationale" in action_data and not isinstance(action_data["rationale"], str):
            raise ValueError("INVALID_PROPOSED_ACTION: rationale must be a string")
        if "estimated_credits" in action_data and (not isinstance(action_data["estimated_credits"], (int, float)) or action_data["estimated_credits"] < 0):
            raise ValueError("INVALID_PROPOSED_ACTION: estimated_credits must be non-negative")
        return ProposedAction.model_validate(action_data)

    async def acomplete(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Asynchronously dispatches completion request to the live vLLM endpoint using httpx.AsyncClient.
        Never returns synthetic or mock actions; raises explicitly when unconfigured or unreachable.
        """
        req_payload = self.build_completion_request(prompt, options)
        req_payload["model"] = self.resolve_served_model()
        active_base_url = self.resolve_active_endpoint()
        if not active_base_url:
            raise RuntimeError(
                "COGNITION_NOT_CONFIGURED: No live cognition endpoint is configured. "
                "Set COGNITION_BASE_URL or OPENAI_BASE_URL to the active OpenAI-compatible runtime."
            )

        endpoint = f"{active_base_url.rstrip('/')}/chat/completions"
        start_time = time.time()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Keystone/2.0",
        }
        api_key = self.resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(endpoint, json=req_payload, headers=headers)
                resp.raise_for_status()
                raw_data = resp.json()
                latency_ms = int((time.time() - start_time) * 1000)
                raw_data["latency_ms"] = latency_ms
                return self.parse_response(raw_data, prompt=prompt)
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:600]
            raise ConnectionError(
                f"COGNITION_HTTP_{exc.response.status_code}: Live cognition endpoint '{endpoint}' failed: {body or exc.response.reason_phrase}"
            ) from exc
        except Exception as exc:
            raise ConnectionError(
                f"COGNITION_UNREACHABLE: Live cognition endpoint '{endpoint}' failed ({type(exc).__name__}: {exc}). "
                "Zero synthetic or mock responses are permitted."
            ) from exc

    def complete(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Synchronously dispatches completion request to the live vLLM endpoint.
        Dynamically discovers active Kaggle/Colab cognition tunnels via WorkerBridge or env.
        Never returns synthetic or mock actions; raises explicitly when unconfigured or unreachable.
        """
        req_payload = self.build_completion_request(prompt, options)
        req_payload["model"] = self.resolve_served_model()
        active_base_url = self.resolve_active_endpoint()
        if not active_base_url:
            raise RuntimeError(
                "COGNITION_NOT_CONFIGURED: No live cognition endpoint is configured. "
                "Set COGNITION_BASE_URL or OPENAI_BASE_URL to the active OpenAI-compatible runtime."
            )

        endpoint = f"{active_base_url.rstrip('/')}/chat/completions"
        start_time = time.time()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Keystone/2.0",
        }
        api_key = self.resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(endpoint, json=req_payload, headers=headers)
                resp.raise_for_status()
                raw_data = resp.json()
                latency_ms = int((time.time() - start_time) * 1000)
                raw_data["latency_ms"] = latency_ms
                return self.parse_response(raw_data, prompt=prompt)
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:600]
            raise ConnectionError(
                f"COGNITION_HTTP_{exc.response.status_code}: Live cognition endpoint '{endpoint}' failed: {body or exc.response.reason_phrase}"
            ) from exc
        except Exception as exc:
            raise ConnectionError(
                f"COGNITION_UNREACHABLE: Live cognition endpoint '{endpoint}' failed ({type(exc).__name__}: {exc}). "
                "Zero synthetic or mock responses are permitted."
            ) from exc


# Alias for versatility
CognitionClient = CognitionConnector
