"""
KEYSTONE Audio & Speech API Router (/v1/audio).
Exposes ElevenLabs voice catalogs, speech synthesis, and audio asset registration.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.session import get_db
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.storage.service import (
    AssetStorageService,
    generate_signed_url,
    generate_storage_key,
)
from services.audio.src.elevenlabs import (
    elevenlabs_client,
    PREMIER_VOICES,
    ELEVENLABS_DEFAULT_MODEL,
)

router = APIRouter(prefix="/v1/audio", tags=["Audio"])


class GenerateSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize into speech")
    voice_id: Optional[str] = Field("21m00Tcm4TlvDq8ikWAM", description="ElevenLabs voice ID")
    voice_settings: Optional[Dict[str, Any]] = Field(default=None, description="Voice settings override")
    project_id: Optional[str] = Field(default=None, description="Optional project ID for asset association")
    save_asset: bool = Field(default=True, description="Whether to register synthesized audio as a durable asset")


@router.get("/config", summary="Get ElevenLabs TTS integration configuration")
async def get_audio_config() -> Dict[str, Any]:
    """Returns the current audio and ElevenLabs TTS configuration status."""
    return {
        "status": "ok",
        "configured": elevenlabs_client.is_configured(),
        "provider": "elevenlabs",
        "default_model": ELEVENLABS_DEFAULT_MODEL,
        "default_voice": "21m00Tcm4TlvDq8ikWAM",
        "voice_count": len(PREMIER_VOICES),
    }


@router.get("/voices", summary="List available ElevenLabs and curated voices")
async def list_voices() -> Dict[str, Any]:
    """Retrieves available ElevenLabs voices or returns curated premier voices."""
    voices = await run_in_threadpool(elevenlabs_client.list_voices)
    return {
        "status": "ok",
        "count": len(voices),
        "voices": voices,
        "has_api_key": elevenlabs_client.is_configured(),
    }


@router.post("/speech", summary="Synthesize speech from text")
async def synthesize_speech(
    req: GenerateSpeechRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Synthesizes text into audio using ElevenLabs (with automatic local formant synthesis fallback)."""
    voice_id = req.voice_id or "21m00Tcm4TlvDq8ikWAM"
    audio_bytes, mime_type, meta = await run_in_threadpool(
        elevenlabs_client.generate_speech,
        req.text,
        voice_id=voice_id,
        voice_settings=req.voice_settings,
    )

    if not req.save_asset:
        ext = "mp3" if "mpeg" in mime_type else "wav"
        filename = f"speech_{uuid.uuid4().hex[:8]}.{ext}"
        return Response(
            content=audio_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Audio-Provider": meta.get("provider", "elevenlabs"),
            }
        )

    # Persist as durable asset
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    ext = ".mp3" if "mpeg" in mime_type else ".wav"
    raw_filename = f"speech_{asset_id[:8]}{ext}"
    storage_key = generate_storage_key(tenant_id, asset_id, raw_filename)

    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, audio_bytes, mime_type)

    match_voice = next((v for v in PREMIER_VOICES if v["voice_id"] == voice_id), {})
    voice_name = match_voice.get("name", "Custom Voice")

    asset = await asset_repo.create_asset(
        id=asset_id,
        filename=raw_filename,
        mime_type=mime_type,
        byte_size=len(audio_bytes),
        storage_key=storage_key,
        project_id=req.project_id,
        media_type="audio",
        storage_provider=storage.provider.__class__.__name__,
        metadata={
            "kind": "tts_speech",
            "script": req.text,
            "voice_id": voice_id,
            "voice_name": voice_name,
            "provider": meta.get("provider", "elevenlabs"),
            "audio_mime": mime_type
        }
    )

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
        "voice_id": voice_id,
        "voice_name": voice_name,
    }
