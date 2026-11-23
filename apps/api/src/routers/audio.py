"""
KEYSTONE Audio & Speech API Router (/v1/audio).
Exposes ElevenLabs voice catalogs, speech synthesis, and audio asset registration.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user, require_admin
from apps.api.src.db.models import User
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.services.gate import GateService, ensure_job_for_receipt
from apps.api.src.storage.service import (
    AssetStorageService,
    generate_signed_url,
    generate_storage_key,
)
from services.audio.src.elevenlabs import (
    elevenlabs_client,
    ELEVENLABS_DEFAULT_MODEL,
)

router = APIRouter(prefix="/v1/audio", tags=["Audio"])


class GenerateSpeechRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize into speech")
    voice_id: Optional[str] = Field(default=None, description="Live ElevenLabs or local SAPI voice ID")
    voice_settings: Optional[Dict[str, Any]] = Field(default=None, description="Voice settings override")
    project_id: Optional[str] = Field(default=None, description="Optional project ID for asset association")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for content mode resolution")
    as_persona: Optional[str] = Field(default=None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(default=None, description="Optional persona ID (alias for `as`)")
    save_asset: bool = Field(default=True, description="Whether to register synthesized audio as a durable asset")


class AudioConfigUpdateRequest(BaseModel):
    elevenlabs_api_key: Optional[str] = Field(None, description="Live ElevenLabs API key")
    base_url: Optional[str] = Field(None, description="Optional ElevenLabs base URL")


@router.get("/config", summary="Get ElevenLabs TTS integration configuration")
async def get_audio_config() -> Dict[str, Any]:
    """Returns the live audio and ElevenLabs/Windows SAPI TTS configuration status."""
    voices: List[Dict[str, Any]] = []
    voice_error: Optional[str] = None
    try:
        voices = await run_in_threadpool(elevenlabs_client.list_voices)
    except Exception as exc:
        voice_error = f"{type(exc).__name__}: {exc}"
    return {
        "status": "error" if voice_error else "ok",
        "configured": elevenlabs_client.is_configured(),
        "provider": "elevenlabs" if elevenlabs_client.is_configured() else "windows_sapi_speech",
        "default_model": ELEVENLABS_DEFAULT_MODEL if elevenlabs_client.is_configured() else "windows_sapi",
        "default_voice": voices[0]["voice_id"] if voices else None,
        "voice_count": len(voices),
        "error": voice_error,
    }


@router.post("/configure", summary="Configure ElevenLabs API Key at runtime")
async def configure_audio_provider(
    req: AudioConfigUpdateRequest,
    _admin: Any = Depends(require_admin),
) -> Dict[str, Any]:
    import os
    from pathlib import Path
    if req.base_url is not None and ("\r" in req.base_url or "\n" in req.base_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_INPUT: Newline characters are not allowed in base_url",
        )
    if req.elevenlabs_api_key is not None:
        if "\r" in req.elevenlabs_api_key or "\n" in req.elevenlabs_api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_INPUT: Newline characters are not allowed in elevenlabs_api_key",
            )
        clean_key = req.elevenlabs_api_key.strip()
        os.environ["ELEVENLABS_API_KEY"] = clean_key
        repo_root = Path(__file__).resolve().parents[4]
        for env_path in (repo_root / ".env", repo_root / "dist" / ".env"):
            if env_path.parent.exists():
                try:
                    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
                    written = False
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith("ELEVENLABS_API_KEY="):
                            new_lines.append(f"ELEVENLABS_API_KEY={clean_key}")
                            written = True
                        else:
                            new_lines.append(line)
                    if not written:
                        new_lines.append(f"ELEVENLABS_API_KEY={clean_key}")
                    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                except Exception:
                    pass
    return await get_audio_config()


@router.get("/voices", summary="List available live ElevenLabs or local SAPI voices")
async def list_voices() -> Dict[str, Any]:
    """Retrieves live ElevenLabs voices when configured, or live installed Windows SAPI voices."""
    try:
        voices = await run_in_threadpool(elevenlabs_client.list_voices)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AUDIO_VOICES_FAILED: {exc}",
        )
    return {
        "status": "ok",
        "count": len(voices),
        "voices": voices,
        "has_api_key": elevenlabs_client.is_configured(),
    }


@router.post("/speech", summary="Synthesize speech from text")
async def synthesize_speech(
    req: GenerateSpeechRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Synthesizes text into real spoken audio after Gate authorization & KEYSTONE prompt compilation."""
    from packages.prompt_engine import compiler as keystone_prompting

    tenant_id = str(current_user.id)
    target_persona_id = req.as_persona or req.persona_id
    explicit_voice_id = (req.voice_id or "").strip() or None

    receipt = await GateService.authorize_async(
        db,
        user_id=tenant_id,
        intent="speak",
        prompt_text=req.text,
        capability_id="audio.tts",
        arguments={"text": req.text, "voice_id": explicit_voice_id},
        project_id=req.project_id,
        session_id=req.session_id,
        persona_id=target_persona_id,
    )

    persona_voice = receipt.persona_voice or {}
    bound_voice_id = str(persona_voice.get("voice_id") or "").strip() or None
    voice_id = explicit_voice_id or bound_voice_id
    voice_settings = req.voice_settings or persona_voice.get("settings")
    warning: Optional[str] = receipt.warnings[0] if receipt.warnings else None
    if warning:
        response.headers["X-Keystone-Warning"] = warning

    compiled = await keystone_prompting.digest_and_compile_prompt(
        user_text=req.text,
        reference_count=0,
        intent_hint="audio",
        persona_sheet=receipt.persona_sheet,
    )

    try:
        audio_bytes, mime_type, meta = await run_in_threadpool(
            elevenlabs_client.generate_speech,
            req.text,
            voice_id=voice_id,
            voice_settings=voice_settings,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AUDIO_SYNTHESIS_FAILED: {exc}",
        )

    resolved_voice_id = str(meta.get("voice_id") or voice_id or "default")
    resolved_voice_name = str(meta.get("voice_name") or resolved_voice_id)

    if not req.save_asset:
        ext = "mp3" if "mpeg" in mime_type else "wav"
        filename = f"speech_{uuid.uuid4().hex[:8]}.{ext}"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Audio-Provider": meta.get("provider", "elevenlabs"),
            "X-Keystone-Prompt-Hash": compiled.prompt_hash,
        }
        if warning:
            headers["X-Keystone-Warning"] = warning
        return Response(
            content=audio_bytes,
            media_type=mime_type,
            headers=headers,
        )

    # Persist as durable asset
    effective_mature = bool(receipt.mature or receipt.persona_mature)
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    ext = ".mp3" if "mpeg" in mime_type else ".wav"
    raw_filename = f"speech_{asset_id[:8]}{ext}"
    storage_key = generate_storage_key(tenant_id, asset_id, raw_filename)

    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, audio_bytes, mime_type)

    voice_name = resolved_voice_name

    asset = await asset_repo.create_asset(
        id=asset_id,
        filename=raw_filename,
        mime_type=mime_type,
        byte_size=len(audio_bytes),
        storage_key=storage_key,
        project_id=req.project_id,
        media_type="audio",
        storage_provider=storage.provider.__class__.__name__,
        mature=effective_mature,
        metadata={
            "kind": "tts_speech",
            "script": req.text,
            "compiled_prompt": compiled.positive_prompt,
            "prompt_hash": compiled.prompt_hash,
            "voice_id": resolved_voice_id,
            "voice_name": voice_name,
            "provider": meta.get("provider", "elevenlabs"),
            "audio_mime": mime_type,
            "persona_id": receipt.persona_id,
            "persona_version": receipt.persona_version,
        },
    )

    if receipt.persona_id:
        await ensure_job_for_receipt(
            db,
            receipt=receipt,
            user_id=tenant_id,
            project_id=req.project_id,
            capability_id="audio.tts",
            provider_id=str(meta.get("provider") or "elevenlabs"),
            workflow_id="audio_speech",
            output_asset_id=asset.id,
            status_value="COMPLETED",
        )
        dag = LineageDAG(session=db)
        await dag.persist_depicts_edge(
            child_asset_id=asset.id,
            persona_id=receipt.persona_id,
            persona_version=receipt.persona_version or 1,
            job_id=receipt.job_id,
            mature=effective_mature,
        )
    await db.commit()

    signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
    download_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"

    return {
        "status": "ok",
        "asset_id": asset.id,
        "media_type": "audio",
        "mime_type": mime_type,
        "byte_size": len(audio_bytes),
        "download_url": download_url,
        "provider": meta.get("provider", "elevenlabs"),
        "voice_id": resolved_voice_id,
        "voice_name": voice_name,
        "prompt_hash": compiled.prompt_hash,
        "persona_id": receipt.persona_id,
        "persona_version": receipt.persona_version,
        "mature": effective_mature,
        "content_mode": receipt.content_mode,
        "envelope_id": receipt.envelope.envelope_id,
        "warning": warning,
        "warnings": list(receipt.warnings),
    }
