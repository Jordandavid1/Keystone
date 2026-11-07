"""
KEYSTONE Autonomous Cognition Agent & Direct LLM Chat Router (/v1/cognition)
Milestone M2 & Bible § 2, § 10, § 11, § 39 (ADR-002)

Provides:
- Direct interactive conversational chat with pinned cognition model:
  huihui-ai/Huihui-Qwen3.8-27B-abliterated
- Autonomous agent task execution with live internet search & scrape tools,
  studio asset generation dispatch, speech synthesis, and session persistence.
"""

from __future__ import annotations

import os
import re
import json
import time
import uuid
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.session import get_db
from services.cognition.src.client import CognitionConnector, PINNED_CHECKPOINT

router = APIRouter(prefix="/v1/cognition", tags=["Cognition Agent & LLM Chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")
    name: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, description="Conversation history")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(2048, ge=64, le=4096)
    web_search: Optional[bool] = Field(False, description="Enable real-time internet search and source citations")
    allow_generation: Optional[bool] = Field(False, description="Permit autonomous studio image/video/speech generation")


class AgentTaskRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Directive or task for the autonomous agent")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    allow_internet: Optional[bool] = Field(True, description="Permit live web lookup & scraping")
    allow_generation: Optional[bool] = Field(True, description="Permit autonomous studio image/video/speech generation")


# ============================================================================
# Live Internet Search & Web Scraping Utility
# ============================================================================

def live_web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
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
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
                )
            }
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

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


def live_url_scrape(target_url: str) -> Dict[str, Any]:
    """
    Extracts text tokens, headlines, and meta description from a target web page.
    """
    try:
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
                )
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

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


def _probe_live_cognition(active_endpoint: str, api_key: str) -> Dict[str, Any]:
    """Probes the live OpenAI-compatible cognition endpoint (/models) for reachability and latency."""
    if not active_endpoint:
        return {"reachable": False, "latency_ms": 0.0, "models": [], "detail": "OPENAI_BASE_URL is not configured"}
    t0 = time.perf_counter()
    models_url = f"{active_endpoint.rstrip('/')}/models"
    headers = {"User-Agent": "KEYSTONE-CognitionProbe/2.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = urllib.request.Request(models_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            payload = json.loads(raw) if raw.strip() else {}
            models = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")]
            return {
                "reachable": (resp.status == 200),
                "latency_ms": latency_ms,
                "models": models,
                "detail": "Live cognition runtime responding",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "reachable": False,
            "latency_ms": latency_ms,
            "models": [],
            "detail": f"{type(exc).__name__}: {exc}",
        }


def _invoke_live_cognition_completion(
    active_endpoint: str,
    api_key: str,
    served_model: str,
    messages: List[Dict[str, str]],
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

    try:
        vllm_req = urllib.request.Request(
            f"{active_endpoint.rstrip('/')}/chat/completions",
            data=json.dumps(vllm_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(vllm_req, timeout=45.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
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
    probe = _probe_live_cognition(active_endpoint, api_key)

    from services.comfy.src.client import comfy_base_url, is_configured as comfy_configured, ComfyUIClient
    comfy_url = comfy_base_url()
    vram_allocated_gb = 0.0
    vram_total_gb = 0.0
    gpu_label = "No GPU telemetry reported"
    if comfy_url:
        try:
            stats = ComfyUIClient(base_url=comfy_url).get_system_stats()
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


@router.post("/chat", summary="Speak directly with loaded Qwen 27B LLM")
async def chat_with_cognition(
    req: ChatRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Interactive multi-turn conversation with huihui-ai/Huihui-Qwen3.8-27B-abliterated.
    Routes to live vLLM/Kaggle worker or generates comprehensive conversational responses.
    """
    start_time = time.time()
    last_user_msg = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    if not last_user_msg.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPTY_MESSAGE: At least one user message with content is required."
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

    from apps.api.src.keystone import prompting as keystone_prompting
    from packages.prompt_engine.playbooks import PlaybookRegistry
    playbook_obj, _, _ = PlaybookRegistry.classify(last_user_msg)
    compiled_prompt_obj = await keystone_prompting.digest_and_compile_prompt(
        user_text=last_user_msg,
        reference_count=0,
        intent_hint="chat",
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
        internet_findings = live_web_search(clean_q, max_results=3)

    wants_gen = req.allow_generation or any(
        kw in msg_lower for kw in (
            "generate an image", "create an image", "make an image", "render an image",
            "generate image", "create a picture", "draw an image", "generate a photo"
        )
    )

    if wants_gen:
        try:
            from services.comfy.src.client import ComfyUIClient
            from apps.api.src.repositories.assets import AssetRepository
            from apps.api.src.storage import AssetStorageService, generate_storage_key

            gen_prompt = compiled_prompt_obj.positive_prompt
            if internet_findings:
                gen_prompt = f"{gen_prompt}\nContext: Inspired by {internet_findings[0]['title']}: {internet_findings[0]['snippet'][:60]}"

            comfy = ComfyUIClient()
            render_res = comfy.generate_image(
                prompt=gen_prompt,
                width=1024,
                height=576,
                steps=25,
                cfg=7.0,
                mode="text2image"
            )

            asset_id = str(uuid.uuid4())
            storage_key = generate_storage_key(tenant_id, asset_id, f"chat_render_{asset_id[:8]}.png")
            storage = AssetStorageService()
            await storage.provider.put_object(storage_key, render_res["bytes"], render_res["mime_type"])

            asset_repo = AssetRepository(db, tenant_id=tenant_id)
            new_asset = await asset_repo.create_asset(
                id=asset_id,
                filename=f"chat_render_{asset_id[:8]}.png",
                mime_type=render_res["mime_type"],
                byte_size=len(render_res["bytes"]),
                storage_key=storage_key,
                project_id=req.project_id,
                media_type="image",
                storage_provider="local",
                metadata={
                    "title": f"Chat Render — {last_user_msg[:24]}...",
                    "prompt": gen_prompt,
                    "model": PINNED_CHECKPOINT
                }
            )

            from apps.api.src.routers.assets import content_url
            created_assets.append({
                "id": new_asset.id,
                "title": f"Render — {last_user_msg[:24]}...",
                "download_url": content_url(new_asset),
                "media_type": "image",
                "width": 1024,
                "height": 576
            })
        except Exception:
            pass

    # Execute live vLLM completion with KEYSTONE Prompt Engine framing + Auth header (zero simulated fallbacks)
    sys_prompt = (
        f"You are KEYSTONE — the authoritative Prompt Engine with `{PINNED_CHECKPOINT}` "
        f"living inside you (active domain mode: '{playbook_obj.label}', bound skills: {', '.join(playbook_obj.bound_skills)}). "
        "You digest the user's intent and spit out finished, production-ready prompts for "
        "MiniMax H3 Ref2VA (<Picture 1>, <Picture 2>, camera, motion, lighting, audio) and "
        "diffusion models, while conversing directly without moralizing refusals.\n\n"
        f"KEYSTONE Compiled Prompt Digest for current turn:\n{compiled_prompt_obj.positive_prompt}"
    )
    if internet_findings:
        web_context = "\n".join(f"- {f['title']}: {f['snippet']} ({f['url']})" for f in internet_findings)
        sys_prompt += f"\n\nLive Web Intelligence Context:\n{web_context}"

    vllm_messages = [{"role": "system", "content": sys_prompt}]
    for m in req.messages:
        vllm_messages.append({"role": m.role, "content": m.content})

    live_res = _invoke_live_cognition_completion(
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

    if req.session_id:
        try:
            from apps.api.src.repositories.sessions import MessageRepository
            msg_repo = MessageRepository(db)
            await msg_repo.create_message(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                role="user",
                content=last_user_msg
            )
            await msg_repo.create_message(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                role="assistant",
                content=live_response_text,
                metadata={"model": PINNED_CHECKPOINT, "latency_ms": latency_ms, "prompt_hash": compiled_prompt_obj.prompt_hash}
            )
        except Exception:
            pass

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
        "internet_findings": internet_findings,
        "created_assets": created_assets,
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
    Autonomous multi-step agent task execution:
    1. Interprets user prompt via KEYSTONE Prompt Engine & Domain Playbooks.
    2. Performs real-time internet search or URL scraping if requested.
    3. Triggers live ComfyUI image/video generation when requested and configured.
    4. Synthesizes final report in real time via the live KEYSTONE Cognition runtime.
    """
    start_time = time.time()
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    task_text = req.task.strip()
    steps_executed: List[Dict[str, Any]] = []
    internet_findings: List[Dict[str, Any]] = []
    created_assets: List[Dict[str, Any]] = []

    from apps.api.src.keystone import prompting as keystone_prompting
    from packages.prompt_engine.playbooks import PlaybookRegistry
    playbook_obj, _, matched_uc = PlaybookRegistry.classify(task_text)
    compiled_task_prompt = await keystone_prompting.digest_and_compile_prompt(
        user_text=task_text,
        reference_count=0,
        intent_hint="agent",
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
            scrape_res = live_url_scrape(extracted_url)
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

            findings = live_web_search(search_query, max_results=3)
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
            from services.comfy.src.client import ComfyUIClient
            from apps.api.src.repositories.assets import AssetRepository
            from apps.api.src.routers.assets import content_url
            from apps.api.src.storage import AssetStorageService, generate_storage_key

            gen_prompt = compiled_task_prompt.positive_prompt
            if internet_findings:
                context_hint = f"\nWeb Context: {internet_findings[0]['title']} — {internet_findings[0]['snippet'][:80]}"
                gen_prompt = f"{gen_prompt}{context_hint}"

            comfy = ComfyUIClient()
            render_res = comfy.generate_image(
                prompt=gen_prompt,
                width=1024,
                height=576,
                steps=30,
                cfg=7.5,
                mode="text2image"
            )

            asset_id = str(uuid.uuid4())
            storage_key = generate_storage_key(tenant_id, asset_id, f"agent_render_{asset_id[:8]}.png")
            storage = AssetStorageService()
            await storage.provider.put_object(storage_key, render_res["bytes"], render_res["mime_type"])

            asset_repo = AssetRepository(db, tenant_id=tenant_id)
            new_asset = await asset_repo.create_asset(
                id=asset_id,
                filename=f"agent_render_{asset_id[:8]}.png",
                mime_type=render_res["mime_type"],
                byte_size=len(render_res["bytes"]),
                storage_key=storage_key,
                project_id=req.project_id,
                media_type="image",
                storage_provider="local",
                metadata={
                    "title": f"Agent Render — {task_text[:28]}...",
                    "prompt": gen_prompt,
                    "prompt_hash": compiled_task_prompt.prompt_hash,
                    "agent_task_id": task_id,
                    "model": PINNED_CHECKPOINT
                }
            )

            created_assets.append({
                "id": new_asset.id,
                "title": f"Agent Output — {task_text[:24]}...",
                "download_url": content_url(new_asset),
                "media_type": "image",
                "width": 1024,
                "height": 576
            })

            steps_executed.append({
                "step": 3,
                "name": "Autonomous Asset Generation",
                "tool": "comfyui.render",
                "status": "completed",
                "details": f"Generated 1024x576 image asset {new_asset.id[:8]} via live ComfyUI engine"
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

    live_res = _invoke_live_cognition_completion(
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
        "steps_executed": steps_executed,
        "internet_findings": internet_findings,
        "created_assets": created_assets,
        "agent_response": agent_response,
        "latency_ms": latency_ms
    }
