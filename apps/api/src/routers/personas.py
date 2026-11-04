"""
KEYSTONE Personas API Router (/v1/personas).
Manages persistent character identities, avatar assets, and persona speech synthesis.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.models import Persona, Asset
from apps.api.src.db.session import get_db
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.storage.service import (
    AssetStorageService,
    generate_signed_url,
    generate_storage_key,
)
from services.audio.src.elevenlabs import elevenlabs_client, PREMIER_VOICES

router = APIRouter(prefix="/v1/personas", tags=["Personas"])


class CreatePersonaRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Persona name")
    description: Optional[str] = Field(None, description="Persona bio, visual cues, and backstory")
    avatar_asset_id: Optional[str] = Field(None, description="Anchor image asset for persona portrait")
    voice_id: Optional[str] = Field("21m00Tcm4TlvDq8ikWAM", description="ElevenLabs voice ID")
    voice_name: Optional[str] = Field("Rachel (American Calm)", description="Display name for selected voice")
    voice_settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Voice stability, similarity, style")
    personality_traits: Optional[List[str]] = Field(default_factory=list, description="Descriptive traits, e.g. Cyberpunk, Narrator")
    system_prompt: Optional[str] = Field(None, description="System prompt instructions injected into cognition")
    project_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    avatar_asset_id: Optional[str] = None
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    personality_traits: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PersonaSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Script to synthesize into speech")
    voice_id: Optional[str] = Field(None, description="Optional override of persona voice ID")
    voice_settings: Optional[Dict[str, Any]] = None


def format_persona(p: Persona, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "project_id": p.project_id,
        "name": p.name,
        "description": p.description,
        "avatar_asset_id": p.avatar_asset_id,
        "avatar_url": avatar_url,
        "voice_id": p.voice_id,
        "voice_name": p.voice_name,
        "voice_settings": p.voice_settings or {},
        "personality_traits": p.personality_traits or [],
        "system_prompt": p.system_prompt,
        "metadata": p.metadata_ or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("", summary="List personas for current tenant")
async def list_personas(
    project_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    query = select(Persona).where(Persona.owner_id == tenant_id)
    if project_id:
        query = query.where(Persona.project_id == project_id)
    query = query.order_by(Persona.created_at.desc())

    result = await db.execute(query)
    personas = result.scalars().all()

    # Hydrate avatar URLs
    items = []
    for p in personas:
        avatar_url = None
        if p.avatar_asset_id:
            asset_res = await db.execute(select(Asset).where(Asset.id == p.avatar_asset_id))
            asset = asset_res.scalar_one_or_none()
            if asset:
                signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
                avatar_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"
        items.append(format_persona(p, avatar_url=avatar_url))

    return {"count": len(items), "personas": items}


@router.post("", summary="Create a new persona")
async def create_persona(
    req: CreatePersonaRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    persona_id = str(uuid.uuid4())

    # Resolve voice name if not explicitly set
    voice_name = req.voice_name
    if not voice_name and req.voice_id:
        match = next((v for v in PREMIER_VOICES if v["voice_id"] == req.voice_id), None)
        voice_name = match["name"] if match else "Custom ElevenLabs Voice"

    persona = Persona(
        id=persona_id,
        owner_id=tenant_id,
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        avatar_asset_id=req.avatar_asset_id,
        voice_id=req.voice_id or "21m00Tcm4TlvDq8ikWAM",
        voice_name=voice_name or "Rachel (American Calm)",
        voice_settings=req.voice_settings or {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2},
        personality_traits=req.personality_traits or [],
        system_prompt=req.system_prompt,
        metadata_=req.metadata or {}
    )

    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    avatar_url = None
    if persona.avatar_asset_id:
        asset_res = await db.execute(select(Asset).where(Asset.id == persona.avatar_asset_id))
        asset = asset_res.scalar_one_or_none()
        if asset:
            signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
            avatar_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"

    return {"status": "ok", "persona": format_persona(persona, avatar_url=avatar_url)}


@router.get("/{persona_id}", summary="Get persona by ID")
async def get_persona(
    persona_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id).where(Persona.owner_id == tenant_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    avatar_url = None
    if persona.avatar_asset_id:
        asset_res = await db.execute(select(Asset).where(Asset.id == persona.avatar_asset_id))
        asset = asset_res.scalar_one_or_none()
        if asset:
            signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
            avatar_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"

    return {"status": "ok", "persona": format_persona(persona, avatar_url=avatar_url)}


@router.put("/{persona_id}", summary="Update an existing persona")
async def update_persona(
    persona_id: str,
    req: UpdatePersonaRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id).where(Persona.owner_id == tenant_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    if req.name is not None:
        persona.name = req.name
    if req.description is not None:
        persona.description = req.description
    if req.avatar_asset_id is not None:
        persona.avatar_asset_id = req.avatar_asset_id
    if req.voice_id is not None:
        persona.voice_id = req.voice_id
    if req.voice_name is not None:
        persona.voice_name = req.voice_name
    if req.voice_settings is not None:
        persona.voice_settings = req.voice_settings
    if req.personality_traits is not None:
        persona.personality_traits = req.personality_traits
    if req.system_prompt is not None:
        persona.system_prompt = req.system_prompt
    if req.metadata is not None:
        meta = dict(persona.metadata_ or {})
        meta.update(req.metadata)
        persona.metadata_ = meta

    await db.commit()
    await db.refresh(persona)

    avatar_url = None
    if persona.avatar_asset_id:
        asset_res = await db.execute(select(Asset).where(Asset.id == persona.avatar_asset_id))
        asset = asset_res.scalar_one_or_none()
        if asset:
            signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
            avatar_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"

    return {"status": "ok", "persona": format_persona(persona, avatar_url=avatar_url)}


@router.delete("/{persona_id}", summary="Delete a persona")
async def delete_persona(
    persona_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id).where(Persona.owner_id == tenant_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    await db.delete(persona)
    await db.commit()
    return {"status": "ok", "deleted_persona_id": persona_id}


@router.post("/{persona_id}/speak", summary="Synthesize speech audio for persona using ElevenLabs")
async def persona_speak(
    persona_id: str,
    req: PersonaSpeakRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id).where(Persona.owner_id == tenant_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    voice_id = req.voice_id or persona.voice_id or "21m00Tcm4TlvDq8ikWAM"
    voice_settings = req.voice_settings or persona.voice_settings or {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2}

    # Synthesize audio bytes via ElevenLabs client
    audio_bytes, mime_type, meta = await run_in_threadpool(
        elevenlabs_client.generate_speech,
        req.text,
        voice_id=voice_id,
        voice_settings=voice_settings
    )

    # Persist audio as an asset
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    ext = ".mp3" if "mpeg" in mime_type else ".wav"
    raw_filename = f"persona_{persona.name.lower().replace(' ', '_')}_{asset_id[:8]}{ext}"
    storage_key = generate_storage_key(tenant_id, asset_id, raw_filename)

    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, audio_bytes, mime_type)

    asset = await asset_repo.create_asset(
        id=asset_id,
        filename=raw_filename,
        mime_type=mime_type,
        byte_size=len(audio_bytes),
        storage_key=storage_key,
        project_id=persona.project_id,
        media_type="audio",
        storage_provider=storage.provider.__class__.__name__,
        metadata={
            "kind": "persona_speech",
            "persona_id": persona.id,
            "persona_name": persona.name,
            "script": req.text,
            "voice_id": voice_id,
            "voice_name": persona.voice_name,
            "provider": meta.get("provider", "elevenlabs"),
            "audio_mime": mime_type
        }
    )

    signed = generate_signed_url(asset.storage_key, expiry_seconds=1800)
    download_url = f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"

    return {
        "status": "ok",
        "asset_id": asset.id,
        "persona_id": persona.id,
        "persona_name": persona.name,
        "media_type": "audio",
        "mime_type": mime_type,
        "byte_size": len(audio_bytes),
        "download_url": download_url,
        "provider": meta.get("provider", "elevenlabs"),
        "voice_id": voice_id,
        "voice_name": persona.voice_name
    }
