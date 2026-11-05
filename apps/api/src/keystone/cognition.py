"""The seat for KEYSTONE's embedded cognition (Bible sections 10 and 11).

The model lives inside KEYSTONE: the compile step consults it, it proposes a PromptIntent,
and KEYSTONE composes the final prompt from that intent. Nothing here decides how the model
is served or loaded; whatever runs it registers a provider. Providers enforce their own
timeouts. With no provider registered, the compile step records cognition as not connected.

CognitiveRequest and CognitiveResult carry the parts of the Bible's contracts that the
compile step needs.
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

from apps.api.src.keystone.models import CapabilityManifest, PromptIntent


class CognitiveRequest(BaseModel):
    request_id: str
    user_text: str
    intent_hint: Optional[str] = None
    reference_count: int = 0
    capability: CapabilityManifest


class CognitiveResult(BaseModel):
    reasoning_id: str
    intent: PromptIntent
    confidence: float
    observations: Dict[str, Any] = Field(default_factory=dict)


class CognitiveProvider(Protocol):
    async def reason(self, request: CognitiveRequest) -> CognitiveResult:
        ...


_provider: Optional[CognitiveProvider] = None


def register(provider: CognitiveProvider) -> None:
    global _provider
    if not callable(getattr(provider, "reason", None)):
        raise TypeError("a cognitive provider needs an async reason(request) method")
    _provider = provider


def unregister() -> None:
    global _provider
    _provider = None


def current() -> Optional[CognitiveProvider]:
    return _provider


class LiveQwenCognitiveProvider:
    """
    Seats the live embedded reasoning model (huihui-ai/Huihui-Qwen3.8-27B-abliterated /
    OPENAI_MODEL at OPENAI_BASE_URL or COGNITION_BASE_URL) inside KEYSTONE's Prompt Engine.
    """

    async def reason(self, request: CognitiveRequest) -> CognitiveResult:
        from packages.prompt_engine.compiler import compile_to_chat_messages
        from packages.prompt_engine.playbooks import PlaybookRegistry
        from services.cognition.src.client import CognitionConnector, PINNED_CHECKPOINT

        connector = CognitionConnector()
        endpoint = connector.resolve_active_endpoint()
        api_key = connector.resolve_api_key()
        served_model = connector.resolve_served_model()

        pb, confidence, _ = PlaybookRegistry.classify(request.user_text)
        suggestions_desc = [
            f"- {s.get('suggestion_id')}: {s.get('text')}"
            for s in request.capability.metadata.get("prompt_suggestions", [])
            if isinstance(s, dict)
        ]

        anatomy = {
            "role": (
                f"/no_think\nKEYSTONE Embedded Reasoning Core ({PINNED_CHECKPOINT}), operating in "
                f"'{pb.label}' ({pb.id}) mode as the authoritative cinematic & multimodal prompt director."
            ),
            "task": (
                f"Digest the user's request and decompose it into a concise, structured PromptIntent JSON object "
                f"for target capability '{request.capability.capability_id}' ({request.capability.provider_id})."
            ),
            "context": [
                f"User Request: {request.user_text}",
                f"Intent Hint: {request.intent_hint or 'generate'}",
                f"Attached Reference Count: {request.reference_count}",
                *suggestions_desc,
            ],
            "constraints": [
                "Respond ONLY with a valid, compact JSON object matching PromptIntent fields: "
                "objective, subject, environment, visual_style, composition, camera, lighting, mood, motion, "
                "references (list of short strings describing each reference role in order), constraints (list of short strings).",
                "Keep each string concise (under 15 words). Do not output <think> blocks or markdown fences.",
                f"If reference_count is {request.reference_count}, provide exactly {request.reference_count} items in 'references'.",
            ],
            "outputFormat": (
                '{"objective": "...", "subject": "...", "environment": "...", "visual_style": "...", '
                '"composition": "...", "camera": "...", "lighting": "...", "mood": "...", "motion": "...", '
                '"references": [], "constraints": []}'
            ),
            "reasoning": "Output the JSON object immediately without internal monologue.",
        }

        messages = compile_to_chat_messages(anatomy)
        payload = {
            "model": served_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Keystone/2.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            f"{endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        msg_obj = raw.get("choices", [{}])[0].get("message", {})
        content = (msg_obj.get("content") or "").strip()
        import re
        content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        if "</think>" in content:
            content = content.split("</think>", 1)[1].strip()
        if content.startswith("```"):
            lines = [ln for ln in content.splitlines() if not ln.strip().startswith("```")]
            content = "\n".join(lines).strip()
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            content = json_match.group(0)

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Embedded model did not return a JSON object")

        clean_fields: Dict[str, Any] = {"objective": request.user_text}
        for k in ("subject", "environment", "visual_style", "composition", "camera", "lighting", "mood", "motion"):
            val = parsed.get(k)
            if isinstance(val, str) and val.strip():
                clean_fields[k] = val.strip()
        for list_k in ("references", "constraints"):
            val = parsed.get(list_k)
            if isinstance(val, list):
                clean_fields[list_k] = [str(x).strip() for x in val if str(x).strip()]
            elif isinstance(val, str) and val.strip():
                clean_fields[list_k] = [val.strip()]

        intent = PromptIntent(**clean_fields)
        return CognitiveResult(
            reasoning_id=f"reas_{uuid.uuid4().hex[:8]}",
            intent=intent,
            confidence=max(float(confidence), 0.88),
            observations={"playbook": pb.id, "model": PINNED_CHECKPOINT, "served_model": served_model},
        )
