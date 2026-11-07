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


class AudioConfigUpdateRequest(BaseModel):
    elevenlabs_api_key: Optional[str] = Field(None, description="Live ElevenLabs API key")


@router.get("/config", summary="Get ElevenLabs TTS integration configuration")
async def get_audio_config() -> Dict[str, Any]:
    """Returns the current audio and ElevenLabs TTS configuration status."""
    return {
        "status": "ok",
        "configured": elevenlabs_client.is_configured(),
        "provider": "elevenlabs" if elevenlabs_client.is_configured() else "windows_sapi_speech",
        "default_model": ELEVENLABS_DEFAULT_MODEL,
        "default_voice": "21m00Tcm4TlvDq8ikWAM",
        "voice_count": len(PREMIER_VOICES),
    }


@router.post("/configure", summary="Configure ElevenLabs API Key at runtime")
async def configure_audio_provider(req: AudioConfigUpdateRequest) -> Dict[str, Any]:
    import os
    from pathlib import Path
    if req.elevenlabs_api_key is not None:
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
    """Synthesizes text into real spoken audio after KEYSTONE prompt compilation."""
    from apps.api.src.keystone import prompting as keystone_prompting

    compiled = await keystone_prompting.digest_and_compile_prompt(
        user_text=req.text,
        reference_count=0,
        intent_hint="audio",
    )

    voice_id = req.voice_id or "21m00Tcm4TlvDq8ikWAM"
    try:
        audio_bytes, mime_type, meta = await run_in_threadpool(
            elevenlabs_client.generate_speech,
            req.text,
            voice_id=voice_id,
            voice_settings=req.voice_settings,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AUDIO_SYNTHESIS_FAILED: {exc}",
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
                "X-Keystone-Prompt-Hash": compiled.prompt_hash,
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
            "compiled_prompt": compiled.positive_prompt,
            "prompt_hash": compiled.prompt_hash,
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
        "prompt_hash": compiled.prompt_hash,
    }
