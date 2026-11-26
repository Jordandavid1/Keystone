"""
KEYSTONE Autonomous Cognition Agent & Direct LLM Chat Router (/v1/cognition)
Milestone M2 & Bible § 2, § 10, § 11, § 39 (ADR-002)

Provides:
- Direct interactive conversational chat with pinned cognition model:
  OBLITERATUS/Qwen3.8-27B-OBLITERATED
- Autonomous agent task execution with live internet search & scrape tools,
  studio asset generation dispatch, speech synthesis, and session persistence.
"""

from __future__ import annotations

import base64
import os
import re
import json
import tempfile
import time
import uuid
import urllib.parse
import httpx
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.models import Asset
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.services.gate import (
    GateService,
    ensure_job_for_receipt,
    load_persona_reference_media,
)
from services.cognition.src.client import CognitionConnector, PINNED_CHECKPOINT

router = APIRouter(prefix="/v1/cognition", tags=["Cognition Agent & LLM Chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    messages: List[ChatMessage] = Field(..., min_length=1, description="Conversation history")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")
    playbook_id: Optional[Any] = None
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(2048, ge=64, le=4096)
    web_search: Optional[bool] = Field(False, description="Enable real-time internet search and source citations")
    allow_generation: Optional[bool] = Field(False, description="Permit autonomous studio image/video/speech generation")


class AgentTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task: str = Field(..., min_length=1, description="Directive or task for the autonomous agent")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")
    playbook_id: Optional[Any] = None
    allow_internet: Optional[bool] = Field(True, description="Permit live web lookup & scraping")
    allow_generation: Optional[bool] = Field(True, description="Permit autonomous studio image/video/speech generation")


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_id: Optional[str] = Field(None, description="Asset ID to inspect with Qwen-VL")
    prompt: str = Field("Inspect and describe this asset in detail.", min_length=1, description="Inspection prompt")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")
    playbook_id: Optional[Any] = None
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(1024, ge=64, le=4096)


# ============================================================================
# Live Internet Search & Web Scraping Utility
# ============================================================================

async def live_web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Performs real-time web search for information, documentation, and creative research.
    Queries DuckDuckGo HTML without requiring proprietary API keys.
    """
    results: List[Dict[str, str]] = []
    clean_query = query.strip()
    if not clean_query:
        return results

    try:
        encoded_query = urllib.parse.quote_plus(clean_query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
            )
        }
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            html = resp.text

        matches = re.findall(
            r'<div class="result__body"[^>]*>.*?<a class="result__url"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL
        )

        for match in matches[:max_results]:
            target_url = match[0].strip()
            title = re.sub(r'<[^>]+>', '', match[1]).strip()
            snippet = re.sub(r'<[^>]+>', '', match[2]).strip()
            if target_url and snippet:
                results.append({
                    "title": title or clean_query,
                    "url": target_url,
                    "snippet": snippet
                })
    except Exception:
        return []

    return results


def _is_ssrf_safe_url(target_url: str) -> Optional[str]:
    """Validates URL scheme and blocks loopback, private, link-local, multicast, and reserved IPs."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "Invalid URL scheme or missing hostname"
    host = parsed.hostname.lower()
    if host in ("localhost", "169.254.169.254", "metadata.google.internal", "metadata"):
        return "Target host is blocked"
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
            ips = [ipaddress.ip_address(info[4][0]) for info in infos]
        except OSError:
            return "Unable to resolve hostname"
    if not ips:
        return "Unable to resolve hostname"
    for ip in ips:
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return f"Blocked IP address range: {ip}"
    return None


async def live_url_scrape(target_url: str) -> Dict[str, Any]:
    """
    Extracts text tokens, headlines, and meta description from a target web page.
    """
    ssrf_err = _is_ssrf_safe_url(target_url)
    if ssrf_err:
        return {
            "url": target_url,
            "title": target_url,
            "content_summary": "",
            "error": f"SSRF_BLOCKED: {ssrf_err}",
            "status": "failed"
        }
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
            )
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(target_url, headers=headers)
            html = resp.text

        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        page_title = title_match.group(1).strip() if title_match else target_url

        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        clean_text = ' '.join(text.split())[:1200]

        return {
            "url": target_url,
            "title": page_title,
            "content_summary": clean_text,
            "status": "success"
        }
    except Exception as exc:
        return {
            "url": target_url,
            "title": target_url,
            "content_summary": "",
            "error": str(exc),
            "status": "failed"
        }


class CognitionConfigRequest(BaseModel):
    openai_base_url: Optional[str] = Field(None, description="Live OpenAI-compatible cognition tunnel URL")
    openai_api_key: Optional[str] = Field(None, description="Bearer API key for cognition endpoint")
    openai_model: Optional[str] = Field(None, description="Served model alias on the vLLM endpoint")


def _build_tls_context():
    """Build an SSL context loading system trust store certificates (fixes Windows Python 3.14 root CA resolution)."""
    import ssl

    try:
        ctx = ssl.create_default_context()
        ctx.load_default_certs()
        return ctx
    except Exception:
        return True


async def _probe_live_cognition(active_endpoint: str, api_key: str) -> Dict[str, Any]:
    """Probes the live OpenAI-compatible cognition endpoint (/models) for reachability and latency."""
    if not active_endpoint:
        return {"reachable": False, "latency_ms": 0.0, "models": [], "detail": "OPENAI_BASE_URL is not configured"}
    t0 = time.perf_counter()
    models_url = f"{active_endpoint.rstrip('/')}/models"
    headers = {"User-Agent": "KEYSTONE-CognitionProbe/2.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    tls_verify = _build_tls_context()
    try:
        async with httpx.AsyncClient(timeout=4.0, verify=tls_verify) as client:
            resp = await client.get(models_url, headers=headers)
    except httpx.ConnectError as ssl_exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(ssl_exc) and os.getenv("KEYSTONE_ENV", "development").lower() != "production":
            try:
                async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
                    resp = await client.get(models_url, headers=headers)
            except Exception as inner_exc:
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                return {"reachable": False, "latency_ms": latency_ms, "models": [], "detail": f"{type(inner_exc).__name__}: {inner_exc}"}
        else:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            return {"reachable": False, "latency_ms": latency_ms, "models": [], "detail": f"{type(ssl_exc).__name__}: {ssl_exc}"}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "models": [],
            "detail": f"{type(exc).__name__}: {exc}",
        }

    try:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        payload = resp.json() if resp.text.strip() else {}
        models = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")]
        detail = (
            "Live cognition runtime responding"
            if resp.status_code == 200
            else f"Endpoint returned HTTP {resp.status_code} at {models_url} (check if worker/pod is stopped or update URL in Engine Control)"
        )
        return {
            "reachable": (resp.status_code == 200),
            "latency_ms": latency_ms,
            "models": models,
            "detail": detail,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "models": [],
            "detail": f"{type(exc).__name__}: {exc}",
        }


async def _invoke_live_cognition_completion(
    active_endpoint: str,
    api_key: str,
    served_model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    """
    Executes a real-time chat completion against the live KEYSTONE Cognition runtime.
    Never returns canned or simulated responses; raises HTTPException(502) if unreachable.
    """
    if not active_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="COGNITION_NOT_CONFIGURED: OPENAI_BASE_URL is not set. Configure the live KEYSTONE Cognition endpoint first.",
        )

    vllm_payload = {
        "model": served_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Keystone/2.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    tls_verify = _build_tls_context()
    try:
        try:
            async with httpx.AsyncClient(timeout=45.0, verify=tls_verify) as client:
                resp = await client.post(
                    f"{active_endpoint.rstrip('/')}/chat/completions",
                    json=vllm_payload,
                    headers=headers,
                )
        except httpx.ConnectError as ssl_exc:
            if "CERTIFICATE_VERIFY_FAILED" in str(ssl_exc) and os.getenv("KEYSTONE_ENV", "development").lower() != "production":
                async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
                    resp = await client.post(
                        f"{active_endpoint.rstrip('/')}/chat/completions",
                        json=vllm_payload,
                        headers=headers,
                    )
            else:
                raise
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Empty choices returned from cognition endpoint")
        content = (choices[0].get("message", {}) or {}).get("content", "")
        if not content or not content.strip():
            raise RuntimeError("Empty message content returned from cognition endpoint")
        return {
            "content": content,
            "usage": data.get("usage", {}),
            "raw": data,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"COGNITION_BACKEND_UNREACHABLE: Live KEYSTONE Cognition runtime at '{active_endpoint}' "
                f"(model '{served_model}') is unreachable or returned an error: {type(exc).__name__}: {exc}. "
                "Zero simulated or fallback responses are permitted."
            ),
        )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/status", summary="Get Cognition Model & Agent Status")
async def get_cognition_status() -> Dict[str, Any]:
    """
    Returns real-time status of the pinned cognition checkpoint and active ComfyUI worker connection.
    """
    connector = CognitionConnector()
    active_endpoint = connector.resolve_active_endpoint()
    api_key = connector.resolve_api_key()
    served_model = connector.resolve_served_model()
    probe = await _probe_live_cognition(active_endpoint, api_key)

    from services.comfy.src.client import comfy_base_url, is_configured as comfy_configured, ComfyUIClient
    comfy_url = comfy_base_url()
    vram_allocated_gb = 0.0
    vram_total_gb = 0.0
    gpu_label = "No GPU telemetry reported"
    if comfy_url:
        try:
            stats = ComfyUIClient().system_stats()
            devices = stats.get("devices") or []
            if devices:
                total_bytes = sum(float(d.get("vram_total", 0)) for d in devices)
                free_bytes = sum(float(d.get("vram_free", 0)) for d in devices)
                vram_total_gb = round(total_bytes / (1024 ** 3), 2)
                vram_allocated_gb = round(max(0.0, total_bytes - free_bytes) / (1024 ** 3), 2)
                gpu_names = [str(d.get("name", "GPU")) for d in devices]
                gpu_label = ", ".join(gpu_names)
        except Exception:
            pass

    return {
        "status": "ok",
        "online": probe["reachable"],
        "model": PINNED_CHECKPOINT,
        "served_model": served_model,
        "pinned": True,
        "active_endpoint": active_endpoint,
        "cognition_latency_ms": probe["latency_ms"],
        "cognition_detail": probe["detail"],
        "available_models": probe["models"],
        "comfy_endpoint": comfy_url or None,
        "comfy_configured": comfy_configured(),
        "worker_cluster": "keystone-live-runtime",
        "gpus": gpu_label,
        "vram_allocated_gb": vram_allocated_gb,
        "vram_total_gb": vram_total_gb,
        "capabilities": [
            "conversational_chat",
            "reasoning_planning",
            "internet_search",
            "url_scraping",
            "creative_asset_generation",
            "voice_synthesis_coordination",
            "unrestricted_cognition"
        ],
        "state": "READY" if probe["reachable"] else "OFFLINE"
    }


@router.post("/configure", summary="Dynamically Configure Live Cognition Endpoint")
async def configure_cognition_endpoint(req: CognitionConfigRequest) -> Dict[str, Any]:
    """Updates OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_MODEL in memory and .env, then probes live status."""
    from apps.api.src.routers.creative import configure_comfy_runtime, ComfyConfigUpdateRequest
    configure_comfy_runtime(
        ComfyConfigUpdateRequest(
            openai_base_url=req.openai_base_url,
            openai_api_key=req.openai_api_key,
            openai_model=req.openai_model,
        )
    )
    return await get_cognition_status()


async def _render_cognition_asset(
    db: AsyncSession,
    *,
    tenant_id: str,
    receipt: Any,
    prompt: str,
    project_id: Optional[str],
    title: str,
    filename_prefix: str,
    steps: int = 25,
    cfg: float = 7.0,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from apps.api.src.repositories.assets import AssetRepository
    from apps.api.src.routers.assets import content_url
    from apps.api.src.storage import AssetStorageService, generate_storage_key
    from services.comfy.src.client import ComfyUIClient

    gen_prompt = prompt
    if receipt.persona_descriptors and receipt.persona_descriptors not in gen_prompt:
        gen_prompt = f"{gen_prompt}\n\n[Persona: {receipt.persona_descriptors}]"

    ref_bytes: Optional[bytes] = None
    ref_filename: Optional[str] = None
    ref_mature = False
    if receipt.persona_reference_assets:
        loaded = await load_persona_reference_media(
            db,
            tenant_id,
            receipt.persona_reference_assets,
            media_kind="image",
        )
        if loaded:
            p_asset, p_fname, _p_mime, p_bytes = loaded[0]
            ref_bytes = p_bytes
            ref_filename = p_fname
            ref_mature = bool(getattr(p_asset, "mature", False))

    comfy = ComfyUIClient()
    render_res = comfy.generate_image(
        prompt=gen_prompt,
        width=1024,
        height=576,
        steps=steps,
        cfg=cfg,
        reference_image_bytes=ref_bytes,
        reference_filename=ref_filename,
        mode="img2img" if ref_bytes else "text2image",
    )

    effective_mature = bool(receipt.mature or receipt.persona_mature or ref_mature)
    asset_id = str(uuid.uuid4())
    fname = f"{filename_prefix}_{asset_id[:8]}.png"
    storage_key = generate_storage_key(tenant_id, asset_id, fname)
    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, render_res["bytes"], render_res["mime_type"])

    meta: Dict[str, Any] = {
        "title": title,
        "prompt": gen_prompt,
        "model": PINNED_CHECKPOINT,
        "persona_id": receipt.persona_id,
        "persona_version": receipt.persona_version,
    }
    if extra_meta:
        meta.update(extra_meta)

    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    new_asset = await asset_repo.create_asset(
        id=asset_id,
        filename=fname,
        mime_type=render_res["mime_type"],
        byte_size=len(render_res["bytes"]),
        storage_key=storage_key,
        project_id=project_id,
        media_type="image",
        storage_provider="local",
        mature=effective_mature,
        metadata=meta,
    )
    if receipt.persona_id:
        await ensure_job_for_receipt(
            db,
            receipt=receipt,
            user_id=tenant_id,
            project_id=project_id,
            capability_id="image.generation",
            provider_id="comfyui",
            workflow_id="cognition_render",
            output_asset_id=new_asset.id,
            status_value="COMPLETED",
        )
        dag = LineageDAG(session=db)
        await dag.persist_depicts_edge(
            child_asset_id=new_asset.id,
            persona_id=receipt.persona_id,
            persona_version=receipt.persona_version or 1,
            job_id=receipt.job_id,
            mature=effective_mature,
        )
    await db.commit()

    return {
        "id": new_asset.id,
        "title": title,
        "download_url": content_url(new_asset),
        "media_type": "image",
        "width": render_res.get("width", 1024),
        "height": render_res.get("height", 576),
        "mature": effective_mature,
        "persona_id": receipt.persona_id,
        "persona_version": receipt.persona_version,
    }


@router.post("/chat", summary="Speak directly with loaded Qwen 27B LLM")
async def chat_with_cognition(
    req: ChatRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Interactive multi-turn conversation with OBLITERATUS/Qwen3.8-27B-OBLITERATED.
    Routes through the Gate (with optional `as: persona_id` sheet injection) to live vLLM/worker.
    """
    start_time = time.time()
    last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    if not last_user_msg.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPTY_MESSAGE: At least one user message with content is required."
        )

    target_persona_id = req.as_persona or req.persona_id
    receipt = await GateService.authorize_async(
        db,
        user_id=tenant_id,
        intent="chat",
        prompt_text=last_user_msg,
        capability_id="cognition.reasoning",
        arguments={"temperature": req.temperature, "max_tokens": req.max_tokens},
        project_id=req.project_id,
        session_id=req.session_id,
        persona_id=target_persona_id,
        playbook=req.playbook_id,
    )

    connector = CognitionConnector()
    active_endpoint = connector.resolve_active_endpoint()
    api_key = connector.resolve_api_key()
    served_model = connector.resolve_served_model()
    live_response_text: Optional[str] = None
    prompt_tokens = sum(max(1, len(m.content.split())) for m in req.messages)
    completion_tokens = 0
    internet_findings: List[Dict[str, Any]] = []
    created_assets: List[Dict[str, Any]] = []

    from packages.prompt_engine import compiler as keystone_prompting
    from packages.prompt_engine.playbooks import PlaybookRegistry
    playbook_obj, _, _ = PlaybookRegistry.classify(last_user_msg)
    compiled_prompt_obj = await keystone_prompting.digest_and_compile_prompt(
        user_text=last_user_msg,
        reference_count=len(receipt.persona_reference_assets),
        intent_hint="chat",
        persona_sheet=receipt.persona_sheet,
    )

    msg_lower = last_user_msg.lower()
    wants_search = req.web_search or any(
        kw in msg_lower for kw in (
            "search the web", "search the internet", "look up on the internet",
            "look up online", "find online", "search for", "google", "browse online",
            "what's the latest", "whats the latest", "current 2026", "recent trends"
        )
    )

    if wants_search:
        clean_q = re.sub(
            r'\b(search the web for|search the internet for|look up on the internet|find online|search for|google|can you search)\b',
            '',
            last_user_msg,
            flags=re.IGNORECASE
        ).strip() or last_user_msg
        internet_findings = await live_web_search(clean_q, max_results=3)

    wants_gen = req.allow_generation or any(
        kw in msg_lower for kw in (
            "generate an image", "create an image", "make an image", "render an image",
            "generate image", "create a picture", "draw an image", "generate a photo"
        )
    )

    generation_error: Optional[str] = None
    if wants_gen:
        try:
            gen_prompt = compiled_prompt_obj.positive_prompt
            if internet_findings:
                gen_prompt = f"{gen_prompt}\nContext: Inspired by {internet_findings[0]['title']}: {internet_findings[0]['snippet'][:60]}"
            gen_receipt = await GateService.authorize_async(
                db,
                user_id=tenant_id,
                intent="generate",
                prompt_text=last_user_msg,
                capability_id="image.generation",
                arguments={"prompt": gen_prompt},
                project_id=req.project_id,
                session_id=req.session_id,
                persona_id=target_persona_id,
                playbook=req.playbook_id,
            )
            created_assets.append(
                await _render_cognition_asset(
                    db,
                    tenant_id=tenant_id,
                    receipt=gen_receipt,
                    prompt=gen_prompt,
                    project_id=req.project_id,
                    title=f"Render — {last_user_msg[:24]}",
                    filename_prefix="chat_render",
                    steps=25,
                    cfg=7.0,
                )
            )
        except Exception as gen_err:
            generation_error = f"{type(gen_err).__name__}: {gen_err}"

    # Execute live vLLM completion with Gate-compiled mode/persona system framing
    sys_prompt = (
        f"{receipt.compiled_prompt}\n\n"
        f"You are KEYSTONE — the authoritative Prompt Engine with `{PINNED_CHECKPOINT}` "
        f"living inside you (active domain mode: '{playbook_obj.label}', bound skills: {', '.join(playbook_obj.bound_skills)}). "
        "You digest the user's intent and produce finished, production-ready prompts for "
        "MiniMax H3 Ref2VA (<Picture 1>, <Picture 2>, camera, motion, lighting, audio) and "
        "diffusion models.\n\n"
        f"KEYSTONE Compiled Prompt Digest for current turn:\n{compiled_prompt_obj.positive_prompt}"
    )
    if generation_error:
        sys_prompt += f"\n\nLive ComfyUI Image Generation Error (report honestly, do not fabricate outputs):\n{generation_error}"
    if internet_findings:
        web_context = "\n".join(f"- {f['title']}: {f['snippet']} ({f['url']})" for f in internet_findings)
        sys_prompt += f"\n\nLive Web Intelligence Context:\n{web_context}"

    vllm_messages: List[Dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
    for m in req.messages:
        vllm_messages.append({"role": m.role, "content": m.content})

    live_res = await _invoke_live_cognition_completion(
        active_endpoint=active_endpoint,
        api_key=api_key,
        served_model=served_model,
        messages=vllm_messages,
        temperature=req.temperature if req.temperature is not None else 0.7,
        max_tokens=req.max_tokens or 2048,
    )
    live_response_text = live_res["content"]
    usage = live_res.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", prompt_tokens))
    completion_tokens = int(usage.get("completion_tokens", max(1, len(live_response_text.split()))))

    latency_ms = max(int((time.time() - start_time) * 1000), 1)
    response_id = f"chatcmpl-{uuid.uuid4().hex[:10]}"

    session_persist_error: Optional[str] = None
    if req.session_id:
        try:
            from apps.api.src.repositories.sessions import MessageRepository
            msg_repo = MessageRepository(db)
            await msg_repo.create_message(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                role="user",
                content=last_user_msg,
                user_id=tenant_id,
            )
            await msg_repo.create_message(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                role="assistant",
                content=live_response_text,
                metadata={"model": PINNED_CHECKPOINT, "latency_ms": latency_ms, "prompt_hash": compiled_prompt_obj.prompt_hash},
                user_id=tenant_id,
            )
            await db.commit()
        except Exception as persist_err:
            session_persist_error = f"{type(persist_err).__name__}: {persist_err}"

    return {
        "id": response_id,
        "model": PINNED_CHECKPOINT,
        "served_model": served_model,
        "message": {
            "role": "assistant",
            "content": live_response_text
        },
        "compiled_prompt": compiled_prompt_obj.positive_prompt,
        "prompt_hash": compiled_prompt_obj.prompt_hash,
        "content_mode": receipt.content_mode,
        "envelope_id": receipt.envelope.envelope_id,
        "persona": receipt.persona_summary,
        "internet_findings": internet_findings,
        "created_assets": created_assets,
        "generation_error": generation_error,
        "session_persist_error": session_persist_error,
        "reasoning_id": f"reas_{uuid.uuid4().hex[:8]}",
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        },
        "latency_ms": latency_ms
    }


@router.post("/agent-task", summary="Instruct autonomous agent to perform web & workspace tasks")
async def execute_agent_task(
    req: AgentTaskRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Autonomous multi-step agent task execution routed through the Gate with optional `as: persona_id`.
    """
    start_time = time.time()
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    task_text = req.task.strip()
    steps_executed: List[Dict[str, Any]] = []
    internet_findings: List[Dict[str, Any]] = []
    created_assets: List[Dict[str, Any]] = []

    target_persona_id = req.as_persona or req.persona_id
    receipt = await GateService.authorize_async(
        db,
        user_id=tenant_id,
        intent="agent_task",
        prompt_text=task_text,
        capability_id="cognition.reasoning",
        arguments={"allow_internet": req.allow_internet, "allow_generation": req.allow_generation},
        project_id=req.project_id,
        session_id=req.session_id,
        persona_id=target_persona_id,
        playbook=req.playbook_id,
    )

    from packages.prompt_engine import compiler as keystone_prompting
    from packages.prompt_engine.playbooks import PlaybookRegistry
    playbook_obj, _, _matched_uc = PlaybookRegistry.classify(task_text)
    compiled_task_prompt = await keystone_prompting.digest_and_compile_prompt(
        user_text=task_text,
        reference_count=len(receipt.persona_reference_assets),
        intent_hint="agent",
        persona_sheet=receipt.persona_sheet,
    )

    steps_executed.append({
        "step": 1,
        "name": "KEYSTONE Prompt Compilation & Playbook Binding",
        "tool": f"keystone.compiler ({playbook_obj.id})",
        "status": "completed",
        "details": f"Compiled prompt hash {compiled_task_prompt.prompt_hash[:12]}... under playbook '{playbook_obj.label}'"
    })

    wants_internet = req.allow_internet and any(
        kw in task_text.lower() for kw in (
            "internet", "web", "look up", "lookup", "search", "google", "find online", "recent", "news", "trend", "http"
        )
    )

    extracted_url = None
    url_match = re.search(r'https?://[^\s]+', task_text)
    if url_match:
        extracted_url = url_match.group(0)

    if wants_internet:
        if extracted_url:
            scrape_res = await live_url_scrape(extracted_url)
            if scrape_res.get("content_summary"):
                internet_findings.append({
                    "title": scrape_res.get("title", extracted_url),
                    "url": extracted_url,
                    "snippet": scrape_res.get("content_summary", "")
                })
            steps_executed.append({
                "step": 2,
                "name": "Live URL Extraction",
                "tool": "firecrawl.scrape",
                "status": scrape_res.get("status", "completed"),
                "details": f"Scraped live content from {extracted_url}"
            })
        else:
            search_query = re.sub(
                r'\b(look up|search for|find on the internet|search the internet for|use the internet and)\b',
                '',
                task_text,
                flags=re.IGNORECASE
            ).strip()
            if not search_query:
                search_query = task_text

            findings = await live_web_search(search_query, max_results=3)
            internet_findings.extend(findings)
            steps_executed.append({
                "step": 2,
                "name": "Live Internet Search",
                "tool": "web.search",
                "status": "completed",
                "details": f"Queried internet for '{search_query[:40]}...', retrieved {len(findings)} source citations"
            })

    wants_generation = req.allow_generation and any(
        kw in task_text.lower() for kw in (
            "generate", "render", "create image", "create a picture", "make an image", "draw", "upscale", "visualize", "produce"
        )
    )

    if wants_generation:
        try:
            gen_prompt = compiled_task_prompt.positive_prompt
            if internet_findings:
                context_hint = f"\nWeb Context: {internet_findings[0]['title']} — {internet_findings[0]['snippet'][:80]}"
                gen_prompt = f"{gen_prompt}{context_hint}"
            gen_receipt = await GateService.authorize_async(
                db,
                user_id=tenant_id,
                intent="generate",
                prompt_text=task_text,
                capability_id="image.generation",
                arguments={"prompt": gen_prompt},
                project_id=req.project_id,
                session_id=req.session_id,
                persona_id=target_persona_id,
                playbook=req.playbook_id,
            )
            rendered = await _render_cognition_asset(
                db,
                tenant_id=tenant_id,
                receipt=gen_receipt,
                prompt=gen_prompt,
                project_id=req.project_id,
                title=f"Agent Output — {task_text[:24]}...",
                filename_prefix="agent_render",
                steps=30,
                cfg=7.5,
                extra_meta={
                    "prompt_hash": compiled_task_prompt.prompt_hash,
                    "agent_task_id": task_id,
                },
            )
            created_assets.append(rendered)
            steps_executed.append({
                "step": 3,
                "name": "Autonomous Asset Generation",
                "tool": "comfyui.render",
                "status": "completed",
                "details": f"Generated 1024x576 image asset {rendered['id'][:8]} via live ComfyUI engine"
            })
        except Exception as gen_err:
            steps_executed.append({
                "step": 3,
                "name": "Autonomous Asset Generation",
                "tool": "comfyui.render",
                "status": "failed",
                "details": f"Live ComfyUI error: {gen_err}"
            })

    connector = CognitionConnector()
    active_endpoint = connector.resolve_active_endpoint()
    api_key = connector.resolve_api_key()
    served_model = connector.resolve_served_model()

    agent_sys_prompt = (
        f"{receipt.compiled_prompt}\n\n"
        f"You are KEYSTONE Autonomous Agent powered by `{PINNED_CHECKPOINT}` "
        f"(active playbook: '{playbook_obj.label}', bound skills: {', '.join(playbook_obj.bound_skills)}).\n"
        f"Compiled KEYSTONE Task Digest:\n{compiled_task_prompt.positive_prompt}"
    )
    if internet_findings:
        web_ctx = "\n".join(f"- {f['title']}: {f['snippet']} ({f['url']})" for f in internet_findings)
        agent_sys_prompt += f"\n\nLive Web Intelligence Findings:\n{web_ctx}"
    if created_assets:
        ast_ctx = "\n".join(f"- Asset {a['id']} ({a['title']}): {a['download_url']}" for a in created_assets)
        agent_sys_prompt += f"\n\nRendered Studio Assets:\n{ast_ctx}"

    live_res = await _invoke_live_cognition_completion(
        active_endpoint=active_endpoint,
        api_key=api_key,
        served_model=served_model,
        messages=[
            {"role": "system", "content": agent_sys_prompt},
            {"role": "user", "content": task_text},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    agent_response = live_res["content"]
    latency_ms = max(int((time.time() - start_time) * 1000), 1)

    return {
        "status": "completed",
        "task_id": task_id,
        "model": PINNED_CHECKPOINT,
        "served_model": served_model,
        "compiled_prompt": compiled_task_prompt.positive_prompt,
        "prompt_hash": compiled_task_prompt.prompt_hash,
        "content_mode": receipt.content_mode,
        "envelope_id": receipt.envelope.envelope_id,
        "persona": receipt.persona_summary,
        "steps_executed": steps_executed,
        "internet_findings": internet_findings,
        "created_assets": created_assets,
        "agent_response": agent_response,
        "latency_ms": latency_ms
    }


@router.post("/analyze", summary="Multimodal Qwen-VL asset inspection through the Gate")
async def analyze_asset(
    req: AnalyzeRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Inspects an image/video/audio asset (with optional `as: persona_id` context)
    through the Gate using live multimodal Qwen-VL completion.
    """
    start_time = time.time()
    asset_obj: Optional[Asset] = None
    if req.asset_id:
        res = await db.execute(
            select(Asset).where(
                Asset.id == str(req.asset_id),
                Asset.user_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset_obj = res.scalar_one_or_none()
        if asset_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    target_persona_id = req.as_persona or req.persona_id
    receipt = await GateService.authorize_async(
        db,
        user_id=tenant_id,
        intent="analyze",
        prompt_text=req.prompt,
        capability_id="analysis.inspect",
        arguments={"asset_id": req.asset_id},
        project_id=req.project_id or (asset_obj.project_id if asset_obj else None),
        session_id=req.session_id,
        persona_id=target_persona_id,
        input_asset_ids=[req.asset_id] if req.asset_id else [],
        playbook=req.playbook_id,
    )

    if asset_obj is not None and getattr(asset_obj, "mature", False) and receipt.content_mode == "sfw":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MATURE_ASSET_BLOCKED_IN_SFW",
                "message": "Mature asset cannot be analyzed in SFW mode.",
            },
        )

    from packages.prompt_engine import compiler as keystone_prompting
    compiled_obj = await keystone_prompting.digest_and_compile_prompt(
        user_text=req.prompt,
        reference_count=1 if asset_obj else 0,
        intent_hint="analyze",
        persona_sheet=receipt.persona_sheet,
    )

    user_content: Any = req.prompt
    if asset_obj is not None:
        from apps.api.src.storage.service import AssetStorageService
        storage = AssetStorageService()
        try:
            raw_bytes = await storage.provider.get_object(asset_obj.storage_key)
        except FileNotFoundError:
            raw_bytes = b""

        mime = (asset_obj.mime_type or "application/octet-stream").split(";")[0].strip().lower()
        asset_summary = (
            f"Asset ID: {asset_obj.id}, type: {asset_obj.asset_type}, mime: {mime}, "
            f"filename: {asset_obj.filename or asset_obj.storage_key.split('/')[-1]}"
        )
        if asset_obj.width and asset_obj.height:
            asset_summary += f", dimensions: {asset_obj.width}x{asset_obj.height}"

        if raw_bytes and (asset_obj.asset_type == "image" or mime.startswith("image/")):
            b64 = base64.b64encode(raw_bytes).decode("ascii")
            user_content = [
                {"type": "text", "text": f"{req.prompt}\n\n[{asset_summary}]"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]
        elif raw_bytes and (asset_obj.asset_type == "video" or mime.startswith("video/")):
            frame_b64: Optional[str] = None
            try:
                from services.comfy.src.video_ops import extract_video_frames
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path = Path(tmp.name)
                try:
                    frames = extract_video_frames(tmp_path)
                    if frames:
                        frame_b64 = base64.b64encode(frames[len(frames) // 2]).decode("ascii")
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
            except Exception:
                frame_b64 = None

            if frame_b64:
                user_content = [
                    {"type": "text", "text": f"{req.prompt}\n\n[{asset_summary} (representative video keyframe attached)]"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{frame_b64}"}},
                ]
            else:
                user_content = f"{req.prompt}\n\n[{asset_summary}]"
        else:
            user_content = f"{req.prompt}\n\n[{asset_summary}]"

    connector = CognitionConnector()
    active_endpoint = connector.resolve_active_endpoint()
    api_key = connector.resolve_api_key()
    served_model = connector.resolve_served_model()

    live_res = await _invoke_live_cognition_completion(
        active_endpoint=active_endpoint,
        api_key=api_key,
        served_model=served_model,
        messages=[
            {"role": "system", "content": receipt.compiled_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=req.temperature if req.temperature is not None else 0.3,
        max_tokens=req.max_tokens or 1024,
    )
    analysis_text = live_res["content"]
    latency_ms = max(int((time.time() - start_time) * 1000), 1)
    usage = live_res.get("usage") or {}

    return {
        "status": "ok",
        "asset_id": req.asset_id,
        "analysis": analysis_text,
        "text": analysis_text,
        "model": PINNED_CHECKPOINT,
        "served_model": served_model,
        "compiled_prompt": compiled_obj.positive_prompt,
        "prompt_hash": compiled_obj.prompt_hash,
        "content_mode": receipt.content_mode,
        "envelope_id": receipt.envelope.envelope_id,
        "persona": receipt.persona_summary,
        "usage": usage,
        "latency_ms": latency_ms,
    }
