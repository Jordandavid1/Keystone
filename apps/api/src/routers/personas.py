"""
Personas Router (Bible v2 §41; ADR-005 PR1 mechanical adaptation).
Exposes REST endpoints for creating, listing, inspecting, and deleting Personas.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import Asset, Persona
from apps.api.src.db.session import get_db
from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.storage.service import generate_signed_url
from services.audio.src.elevenlabs import elevenlabs_client

router = APIRouter(prefix="/v1/personas", tags=["Personas"])


class CreatePersonaRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Persona name")
    description: Optional[str] = Field(None, description="Persona bio, visual cues, and backstory")
    project_id: Optional[str] = Field(None, description="Project to scope this persona to")
    avatar_asset_id: Optional[str] = Field(None, description="Optional asset ID for persona avatar image")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID")
    voice_name: Optional[str] = Field(None, description="Human readable voice label")
    voice_settings: Optional[Dict[str, Any]] = Field(None, description="Voice generation hyperparameters")
    personality_traits: Optional[List[str]] = Field(None, description="List of personality trait keywords")
    system_prompt: Optional[str] = Field(None, description="Dedicated system prompt instructions for persona")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary persona attributes")


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
    voice_settings: Optional[Dict[str, Any]] = Field(None, description="Optional override of voice settings")


def format_persona(p: Persona, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    voice_info = p.voice or {}
    return {
        "id": p.id,
        "version": p.version,
        "user_id": p.user_id,
        "name": p.name,
        "description": p.description,
        "avatar_url": avatar_url,
        "voice_id": voice_info.get("voice_id"),
        "voice_name": voice_info.get("voice_name"),
        "voice_settings": voice_info.get("settings") or {},
        "personality_traits": p.traits.get("personality_traits", []) if p.traits else [],
        "system_prompt": p.backstory,
        "metadata": p.traits or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("", summary="List personas for current tenant")
async def list_personas(
    project_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    query = select(Persona).where(Persona.user_id == tenant_id, Persona.is_current.is_(True))
    query = query.order_by(Persona.created_at.desc())

    result = await db.execute(query)
    personas = result.scalars().all()

    items = []
    for p in personas:
        items.append(format_persona(p))

    return {"status": "ok", "personas": items}


@router.post("", summary="Create a new persona")
async def create_persona(
    req: CreatePersonaRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    persona_id = str(uuid.uuid4())

    voice_id = (req.voice_id or "").strip() or None
    voice_name = (req.voice_name or "").strip() or None
    if not voice_name and voice_id:
        try:
            voices = await run_in_threadpool(elevenlabs_client.list_voices)
            match = next((v for v in voices if v.get("voice_id") == voice_id), None)
            voice_name = match.get("name") if match else voice_id
        except Exception:
            voice_name = voice_id

    voice_payload = {
        "provider": "elevenlabs",
        "voice_id": voice_id or "",
        "voice_name": voice_name or "",
        "settings": req.voice_settings or {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2},
    } if voice_id else None

    traits_payload = dict(req.metadata or {})
    if req.personality_traits:
        traits_payload["personality_traits"] = req.personality_traits

    persona = Persona(
        id=persona_id,
        version=1,
        user_id=tenant_id,
        name=req.name,
        description=req.description,
        traits=traits_payload,
        backstory=req.system_prompt,
        reference_assets=[],
        identity_adapter="reference_set",
        voice=voice_payload,
        mature=False,
        is_current=True,
    )

    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    return {"status": "ok", "persona": format_persona(persona)}


@router.get("/{persona_id}", summary="Get persona by ID")
async def get_persona(
    persona_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == tenant_id, Persona.is_current.is_(True))
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    return {"status": "ok", "persona": format_persona(persona)}


@router.put("/{persona_id}", summary="Update an existing persona")
async def update_persona(
    persona_id: str,
    req: UpdatePersonaRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == tenant_id, Persona.is_current.is_(True))
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    if req.name is not None:
        persona.name = req.name
    if req.description is not None:
        persona.description = req.description
    if req.system_prompt is not None:
        persona.backstory = req.system_prompt
    if req.voice_id is not None or req.voice_settings is not None:
        current_voice = dict(persona.voice or {})
        if req.voice_id is not None:
            current_voice["voice_id"] = req.voice_id
        if req.voice_name is not None:
            current_voice["voice_name"] = req.voice_name
        if req.voice_settings is not None:
            current_voice["settings"] = req.voice_settings
        persona.voice = current_voice
    if req.personality_traits is not None or req.metadata is not None:
        traits = dict(persona.traits or {})
        if req.personality_traits is not None:
            traits["personality_traits"] = req.personality_traits
        if req.metadata is not None:
            traits.update(req.metadata)
        persona.traits = traits

    await db.commit()
    await db.refresh(persona)

    return {"status": "ok", "persona": format_persona(persona)}


@router.delete("/{persona_id}", summary="Delete a persona")
async def delete_persona(
    persona_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    result = await db.execute(
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == tenant_id)
    )
    personas = result.scalars().all()
    if not personas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    for p in personas:
        await db.delete(p)
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
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == tenant_id, Persona.is_current.is_(True))
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    voice_info = persona.voice or {}
    voice_id = (req.voice_id or voice_info.get("voice_id") or "").strip() or None
    voice_settings = req.voice_settings or voice_info.get("settings") or {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2}

    try:
        audio_bytes, mime_type, meta = await run_in_threadpool(
            elevenlabs_client.generate_speech,
            req.text,
            voice_id=voice_id,
            voice_settings=voice_settings
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speech synthesis provider error: {str(exc)}"
        )

    storage = None
    try:
        from apps.api.src.storage.service import storage as default_storage
        storage = default_storage
    except Exception:
        pass

    storage_key = f"tenants/{tenant_id}/personas/{persona_id}/speech_{uuid.uuid4().hex[:8]}.mp3"
    if storage:
        await storage.upload_bytes(storage_key, audio_bytes, mime_type=mime_type)

    asset = Asset(
        id=str(uuid.uuid4()),
        user_id=tenant_id,
        project_id=None,
        asset_type="audio",
        storage_key=storage_key,
        filename=f"persona_{persona.name.lower().replace(' ', '_')}_speech.mp3",
        mime_type=mime_type,
        size_bytes=len(audio_bytes),
        duration_seconds=meta.get("duration_seconds", 0.0),
        mature=False,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    signed_url = generate_signed_url(storage_key, expiry_seconds=3600)
    audio_url = f"/v1/assets/{asset.id}/content?{signed_url.split('?', 1)[1]}"

    return {
        "status": "ok",
        "asset_id": asset.id,
        "audio_url": audio_url,
        "voice_used": voice_id,
        "character_count": len(req.text),
        "metadata": meta
    }
