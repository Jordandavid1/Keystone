"""
Personas Router (Bible v2 §41; ADR-005 PR6).
Exposes REST endpoints for creating, listing, inspecting, immutable versioning,
soft-deleting, and Gate-authorized speech synthesis for Personas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.db.models import Asset, Persona, Project, Session as ChatSession, User
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.services.gate import (
    GateService,
    ensure_job_for_receipt,
    resolve_content_mode,
)
from apps.api.src.storage.service import (
    AssetStorageService,
    generate_signed_url,
    generate_storage_key,
)
from services.audio.src.elevenlabs import elevenlabs_client

router = APIRouter(prefix="/v1/personas", tags=["Personas"])


class PersonaVoiceInput(BaseModel):
    provider: Optional[str] = "elevenlabs"
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class CreatePersonaRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Persona name")
    description: Optional[str] = Field(None, description="Persona bio, visual cues, and backstory")
    project_id: Optional[str] = Field(None, description="Project to scope this persona to")
    avatar_asset_id: Optional[str] = Field(None, description="Optional asset ID for persona avatar image")
    reference_assets: Optional[List[str]] = Field(None, description="Reference asset IDs for identity conditioning")
    identity_adapter: Optional[str] = Field("reference_set", description="Identity adapter: reference_set | ip")
    voice: Optional[PersonaVoiceInput] = Field(None, description="Nested §41 voice binding")
    voice_provider: Optional[str] = Field(None, description="Voice synthesis provider (e.g. elevenlabs)")
    voice_id: Optional[str] = Field(None, description="ElevenLabs or local TTS voice ID")
    voice_name: Optional[str] = Field(None, description="Human readable voice label")
    voice_settings: Optional[Dict[str, Any]] = Field(None, description="Voice generation hyperparameters")
    personality_traits: Optional[List[str]] = Field(None, description="List of personality trait keywords")
    traits: Optional[Union[List[str], Dict[str, Any]]] = Field(None, description="Persona traits list or map")
    backstory: Optional[str] = Field(None, description="Persona backstory / system-prompt fragment")
    system_prompt: Optional[str] = Field(None, description="Dedicated system prompt instructions for persona")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary persona attributes")


class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    project_id: Optional[str] = None
    avatar_asset_id: Optional[str] = None
    reference_assets: Optional[List[str]] = None
    identity_adapter: Optional[str] = None
    voice: Optional[PersonaVoiceInput] = None
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    personality_traits: Optional[List[str]] = None
    traits: Optional[Union[List[str], Dict[str, Any]]] = None
    backstory: Optional[str] = None
    system_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PersonaSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Script to synthesize into speech")
    voice_id: Optional[str] = Field(None, description="Optional override of persona voice ID")
    voice_settings: Optional[Dict[str, Any]] = Field(None, description="Optional override of voice settings")
    project_id: Optional[str] = Field(None, description="Optional project ID for mode resolution")
    session_id: Optional[str] = Field(None, description="Optional session ID for mode resolution")


def _normalize_identity_adapter(raw: Optional[str]) -> str:
    val = (raw or "reference_set").strip().lower().replace("-", "_")
    if val not in ("reference_set", "ip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"INVALID_IDENTITY_ADAPTER: '{raw}' must be 'reference_set' or 'ip'",
        )
    return val


def _build_traits_payload(
    *,
    base_traits: Optional[Dict[str, Any]] = None,
    traits_field: Optional[Union[List[str], Dict[str, Any]]] = None,
    personality_traits: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(base_traits or {})
    if isinstance(metadata, dict):
        payload.update(metadata)
    if isinstance(traits_field, dict):
        payload.update(traits_field)
    elif isinstance(traits_field, list):
        payload["personality_traits"] = [str(t).strip() for t in traits_field if str(t).strip()]
    if personality_traits is not None:
        payload["personality_traits"] = [str(t).strip() for t in personality_traits if str(t).strip()]
    return payload


async def _resolve_voice_payload(
    *,
    existing_voice: Optional[Dict[str, Any]] = None,
    voice_obj: Optional[PersonaVoiceInput] = None,
    voice_provider: Optional[str] = None,
    voice_id: Optional[str] = None,
    voice_name: Optional[str] = None,
    voice_settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    has_update = any(
        x is not None for x in (voice_obj, voice_provider, voice_id, voice_name, voice_settings)
    )
    if not has_update:
        return dict(existing_voice) if isinstance(existing_voice, dict) else None

    merged = dict(existing_voice or {})
    if voice_obj is not None:
        if voice_obj.provider is not None:
            merged["provider"] = voice_obj.provider
        if voice_obj.voice_id is not None:
            merged["voice_id"] = voice_obj.voice_id
        if voice_obj.voice_name is not None:
            merged["voice_name"] = voice_obj.voice_name
        if voice_obj.settings is not None:
            merged["settings"] = dict(voice_obj.settings)

    if voice_provider is not None:
        merged["provider"] = voice_provider.strip() or "elevenlabs"
    if voice_id is not None:
        merged["voice_id"] = voice_id.strip()
    if voice_name is not None:
        merged["voice_name"] = voice_name.strip()
    if voice_settings is not None:
        merged["settings"] = dict(voice_settings)

    vid = str(merged.get("voice_id") or "").strip()
    if not vid and not merged.get("provider"):
        return None
    if not vid and not merged.get("voice_name") and not merged.get("settings"):
        return None

    vname = str(merged.get("voice_name") or "").strip()
    if vid and not vname:
        try:
            voices = await run_in_threadpool(elevenlabs_client.list_voices)
            match = next((v for v in voices if v.get("voice_id") == vid), None)
            vname = str(match.get("name")) if match else vid
        except Exception:
            vname = vid

    return {
        "provider": str(merged.get("provider") or "elevenlabs"),
        "voice_id": vid,
        "voice_name": vname,
        "settings": merged.get("settings") or {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2},
    }


async def _validate_owned_assets(
    db: AsyncSession,
    tenant_id: str,
    asset_ids: List[str],
    *,
    resolved_mode: str,
) -> Dict[str, Asset]:
    if not asset_ids:
        return {}
    unique_ids = list(dict.fromkeys(str(aid).strip() for aid in asset_ids if str(aid).strip()))
    if not unique_ids:
        return {}
    res = await db.execute(
        select(Asset).where(
            Asset.id.in_(unique_ids),
            Asset.user_id == str(tenant_id),
            Asset.deleted_at.is_(None),
        )
    )
    found = {str(a.id): a for a in res.scalars().all()}
    for aid in unique_ids:
        asset = found.get(aid)
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced asset '{aid}' not found",
            )
        if getattr(asset, "mature", False) and resolved_mode == "sfw":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "MATURE_ASSET_BLOCKED_IN_SFW",
                    "message": "Mature asset cannot be attached to an SFW persona.",
                },
            )
    return found


async def _load_scope_objects(
    db: AsyncSession,
    user: User,
    project_id: Optional[str],
    session_id: Optional[str],
) -> tuple[Optional[Project], Optional[ChatSession]]:
    project = None
    if project_id:
        res_p = await db.execute(
            select(Project).where(
                Project.id == str(project_id),
                Project.user_id == str(user.id),
                Project.deleted_at.is_(None),
            )
        )
        project = res_p.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    chat_session = None
    if session_id:
        res_s = await db.execute(
            select(ChatSession).where(
                ChatSession.id == str(session_id),
                ChatSession.user_id == str(user.id),
            )
        )
        chat_session = res_s.scalar_one_or_none()
        if chat_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return project, chat_session


def _resolve_effective_mode(
    user: User,
    project: Optional[Project] = None,
    chat_session: Optional[ChatSession] = None,
    requested_mode: Optional[str] = None,
) -> Literal["sfw", "unrestricted"]:
    if requested_mode in ("sfw", "unrestricted"):
        if requested_mode == "sfw":
            return "sfw"
        return "unrestricted" if bool(getattr(user, "age_verified", False)) else "sfw"
    mode = resolve_content_mode(user, project, chat_session)
    if mode == "unrestricted" and not bool(getattr(user, "age_verified", False)):
        return "sfw"
    return mode


async def _mint_avatar_url(db: AsyncSession, persona: Persona, tenant_id: str) -> Optional[str]:
    avatar_id = getattr(persona, "avatar_asset_id", None)
    if not avatar_id:
        return None
    res = await db.execute(
        select(Asset).where(
            Asset.id == str(avatar_id),
            Asset.user_id == str(tenant_id),
            Asset.deleted_at.is_(None),
        )
    )
    asset = res.scalar_one_or_none()
    if asset is None:
        return None
    signed = generate_signed_url(asset.storage_key, expiry_seconds=3600)
    return f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"


def format_persona(p: Persona, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    voice_info = p.voice or {}
    traits_dict = p.traits if isinstance(p.traits, dict) else {}
    return {
        "id": p.id,
        "version": p.version,
        "user_id": p.user_id,
        "owner_id": p.user_id,
        "project_id": getattr(p, "project_id", None),
        "parent_persona_id": getattr(p, "parent_persona_id", None),
        "avatar_asset_id": getattr(p, "avatar_asset_id", None),
        "name": p.name,
        "description": p.description,
        "avatar_url": avatar_url,
        "reference_assets": list(p.reference_assets or []),
        "identity_adapter": getattr(p, "identity_adapter", "reference_set"),
        "voice": p.voice,
        "voice_provider": voice_info.get("provider"),
        "voice_id": voice_info.get("voice_id") or None,
        "voice_name": voice_info.get("voice_name") or None,
        "voice_settings": voice_info.get("settings") or {},
        "personality_traits": traits_dict.get("personality_traits", []),
        "traits": traits_dict,
        "backstory": p.backstory,
        "system_prompt": p.backstory,
        "metadata": traits_dict,
        "mature": bool(getattr(p, "mature", False)),
        "is_current": bool(getattr(p, "is_current", True)),
        "deleted_at": p.deleted_at.isoformat() if getattr(p, "deleted_at", None) else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("", summary="List personas for current tenant")
async def list_personas(
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    content_mode: Optional[str] = Query(None, description="Optional resolved mode filter: sfw or unrestricted"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    project, chat_session = await _load_scope_objects(db, current_user, project_id, session_id)
    resolved_mode = _resolve_effective_mode(current_user, project, chat_session, content_mode)

    query = select(Persona).where(
        Persona.user_id == tenant_id,
        Persona.is_current.is_(True),
        Persona.deleted_at.is_(None),
    )
    if project_id:
        query = query.where(Persona.project_id == str(project_id))
    if resolved_mode == "sfw":
        query = query.where(Persona.mature.is_(False))
    query = query.order_by(Persona.created_at.desc())

    result = await db.execute(query)
    personas = result.scalars().all()

    items = []
    for p in personas:
        avatar_url = await _mint_avatar_url(db, p, tenant_id)
        items.append(format_persona(p, avatar_url=avatar_url))

    return {"status": "ok", "content_mode": resolved_mode, "personas": items}


@router.post("", summary="Create a new persona")
async def create_persona(
    req: CreatePersonaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    project, _ = await _load_scope_objects(db, current_user, req.project_id, None)
    resolved_mode = resolve_content_mode(current_user, project, None)
    if resolved_mode == "unrestricted" and not bool(getattr(current_user, "age_verified", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "Age verification is required for unrestricted content mode.",
            },
        )

    identity_adapter = _normalize_identity_adapter(req.identity_adapter)
    ref_assets = [str(aid).strip() for aid in (req.reference_assets or []) if str(aid).strip()]
    if req.avatar_asset_id and req.reference_assets is None:
        ref_assets = [req.avatar_asset_id]

    assets_to_check = list(ref_assets)
    if req.avatar_asset_id:
        assets_to_check.append(req.avatar_asset_id)
    await _validate_owned_assets(db, tenant_id, assets_to_check, resolved_mode=resolved_mode)

    voice_payload = await _resolve_voice_payload(
        voice_obj=req.voice,
        voice_provider=req.voice_provider,
        voice_id=req.voice_id,
        voice_name=req.voice_name,
        voice_settings=req.voice_settings,
    )
    traits_payload = _build_traits_payload(
        traits_field=req.traits,
        personality_traits=req.personality_traits,
        metadata=req.metadata,
    )
    backstory = req.backstory if req.backstory is not None else req.system_prompt

    persona_id = str(uuid.uuid4())
    persona = Persona(
        id=persona_id,
        version=1,
        user_id=tenant_id,
        project_id=str(req.project_id) if req.project_id else None,
        parent_persona_id=None,
        avatar_asset_id=str(req.avatar_asset_id) if req.avatar_asset_id else None,
        name=req.name,
        description=req.description,
        traits=traits_payload,
        backstory=backstory,
        reference_assets=list(dict.fromkeys(ref_assets)),
        identity_adapter=identity_adapter,
        voice=voice_payload,
        mature=(resolved_mode == "unrestricted"),
        is_current=True,
        deleted_at=None,
    )

    db.add(persona)
    await db.commit()
    await db.refresh(persona)

    avatar_url = await _mint_avatar_url(db, persona, tenant_id)
    return {"status": "ok", "persona": format_persona(persona, avatar_url=avatar_url)}


@router.get("/{persona_id}", summary="Get persona by ID")
async def get_persona(
    persona_id: str,
    version: Optional[int] = Query(None, ge=1, description="Optional immutable persona version"),
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    content_mode: Optional[str] = Query(None, description="Optional resolved mode filter: sfw or unrestricted"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    project, chat_session = await _load_scope_objects(db, current_user, project_id, session_id)
    resolved_mode = _resolve_effective_mode(current_user, project, chat_session, content_mode)

    stmt = select(Persona).where(
        Persona.id == persona_id,
        Persona.user_id == tenant_id,
        Persona.deleted_at.is_(None),
    )
    if version is not None:
        stmt = stmt.where(Persona.version == version)
    else:
        stmt = stmt.where(Persona.is_current.is_(True))

    result = await db.execute(stmt)
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    if getattr(persona, "mature", False) and resolved_mode == "sfw":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    avatar_url = await _mint_avatar_url(db, persona, tenant_id)
    return {"status": "ok", "persona": format_persona(persona, avatar_url=avatar_url)}


@router.get("/{persona_id}/versions", summary="List immutable versions for a persona")
async def list_persona_versions(
    persona_id: str,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    content_mode: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    project, chat_session = await _load_scope_objects(db, current_user, project_id, session_id)
    resolved_mode = _resolve_effective_mode(current_user, project, chat_session, content_mode)

    stmt = (
        select(Persona)
        .where(
            Persona.id == persona_id,
            Persona.user_id == tenant_id,
            Persona.deleted_at.is_(None),
        )
        .order_by(Persona.version.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    if resolved_mode == "sfw":
        rows = [r for r in rows if not getattr(r, "mature", False)]
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    versions = []
    for row in rows:
        avatar_url = await _mint_avatar_url(db, row, tenant_id)
        versions.append(format_persona(row, avatar_url=avatar_url))
    return {"status": "ok", "persona_id": persona_id, "versions": versions}


async def _create_new_persona_version(
    persona_id: str,
    req: UpdatePersonaRequest,
    current_user: User,
    db: AsyncSession,
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    result = await db.execute(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.user_id == tenant_id,
            Persona.is_current.is_(True),
            Persona.deleted_at.is_(None),
        )
    )
    old = result.scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    target_project_id = req.project_id if req.project_id is not None else getattr(old, "project_id", None)
    project, _ = await _load_scope_objects(db, current_user, target_project_id, None)
    resolved_mode = _resolve_effective_mode(current_user, project, None, None)

    if getattr(old, "mature", False) and resolved_mode == "sfw":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MATURE_PERSONA_BLOCKED_IN_SFW",
                "message": "Mature persona cannot be modified in SFW mode.",
            },
        )

    next_adapter = (
        _normalize_identity_adapter(req.identity_adapter)
        if req.identity_adapter is not None
        else getattr(old, "identity_adapter", "reference_set")
    )
    next_avatar = (
        req.avatar_asset_id if req.avatar_asset_id is not None else getattr(old, "avatar_asset_id", None)
    )
    if req.reference_assets is not None:
        next_refs = list(dict.fromkeys(str(aid).strip() for aid in req.reference_assets if str(aid).strip()))
    else:
        next_refs = list(old.reference_assets or [])
        if req.avatar_asset_id and req.avatar_asset_id not in next_refs:
            next_refs.append(req.avatar_asset_id)

    assets_to_check = list(next_refs)
    if next_avatar:
        assets_to_check.append(next_avatar)
    await _validate_owned_assets(db, tenant_id, assets_to_check, resolved_mode=resolved_mode)

    next_voice = await _resolve_voice_payload(
        existing_voice=old.voice,
        voice_obj=req.voice,
        voice_provider=req.voice_provider,
        voice_id=req.voice_id,
        voice_name=req.voice_name,
        voice_settings=req.voice_settings,
    )
    next_traits = _build_traits_payload(
        base_traits=old.traits if isinstance(old.traits, dict) else {},
        traits_field=req.traits,
        personality_traits=req.personality_traits,
        metadata=req.metadata,
    )
    next_backstory = (
        req.backstory
        if req.backstory is not None
        else (req.system_prompt if req.system_prompt is not None else old.backstory)
    )
    next_mature = bool(getattr(old, "mature", False)) or (resolved_mode == "unrestricted")

    # Mark previous current version non-current BEFORE inserting new current row
    old.is_current = False
    await db.flush()

    new_version = int(old.version) + 1
    new_persona = Persona(
        id=old.id,
        version=new_version,
        user_id=old.user_id,
        project_id=target_project_id,
        parent_persona_id=old.id,
        avatar_asset_id=next_avatar,
        name=req.name if req.name is not None else old.name,
        description=req.description if req.description is not None else old.description,
        traits=next_traits,
        backstory=next_backstory,
        reference_assets=next_refs,
        identity_adapter=next_adapter,
        voice=next_voice,
        mature=next_mature,
        is_current=True,
        deleted_at=None,
    )
    db.add(new_persona)
    await db.commit()
    await db.refresh(new_persona)

    avatar_url = await _mint_avatar_url(db, new_persona, tenant_id)
    return {
        "status": "ok",
        "persona": format_persona(new_persona, avatar_url=avatar_url),
        "previous_version": old.version,
    }


@router.patch("/{persona_id}", summary="Create a new immutable version of a persona")
async def patch_persona(
    persona_id: str,
    req: UpdatePersonaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await _create_new_persona_version(persona_id, req, current_user, db)


@router.put("/{persona_id}", summary="Update persona (creates a new immutable version)")
async def update_persona(
    persona_id: str,
    req: UpdatePersonaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await _create_new_persona_version(persona_id, req, current_user, db)


@router.delete("/{persona_id}", summary="Soft-delete a persona (preserves historical depicts lineage)")
async def delete_persona(
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    result = await db.execute(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.user_id == tenant_id,
            Persona.deleted_at.is_(None),
        )
    )
    personas = result.scalars().all()
    if not personas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    deleted_ts = datetime.now(timezone.utc)
    for p in personas:
        p.deleted_at = deleted_ts
    await db.commit()
    return {
        "status": "ok",
        "deleted_persona_id": persona_id,
        "deleted_at": deleted_ts.isoformat(),
    }


@router.post("/{persona_id}/speak", summary="Synthesize speech audio for persona through the Gate")
async def persona_speak(
    persona_id: str,
    req: PersonaSpeakRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tenant_id = str(current_user.id)
    result = await db.execute(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.user_id == tenant_id,
            Persona.is_current.is_(True),
            Persona.deleted_at.is_(None),
        )
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    voice_info = persona.voice or {}
    bound_voice_id = str(voice_info.get("voice_id") or "").strip() or None
    override_voice_id = (req.voice_id or "").strip() or None
    voice_id = override_voice_id or bound_voice_id
    voice_settings = req.voice_settings or voice_info.get("settings") or {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.2,
    }

    receipt = await GateService.authorize_async(
        db,
        user_id=tenant_id,
        intent="speak",
        prompt_text=req.text,
        capability_id="audio.tts",
        arguments={"text": req.text, "voice_id": voice_id},
        project_id=req.project_id or getattr(persona, "project_id", None),
        session_id=req.session_id,
        persona_id=persona.id,
        persona_version=persona.version,
    )

    warning: Optional[str] = receipt.warnings[0] if receipt.warnings else None
    if warning:
        response.headers["X-Keystone-Warning"] = warning

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
            detail=f"Speech synthesis provider error: {str(exc)}",
        )

    asset_id = str(uuid.uuid4())
    ext = ".mp3" if "mpeg" in mime_type else ".wav"
    safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in persona.name.lower()).strip("_") or "persona"
    raw_filename = f"persona_{safe_name}_{asset_id[:8]}{ext}"
    storage_key = generate_storage_key(tenant_id, asset_id, raw_filename)
    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, audio_bytes, mime_type)

    effective_mature = bool(receipt.mature or getattr(persona, "mature", False))
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset = await asset_repo.create_asset(
        id=asset_id,
        filename=raw_filename,
        mime_type=mime_type,
        byte_size=len(audio_bytes),
        storage_key=storage_key,
        project_id=req.project_id or getattr(persona, "project_id", None),
        media_type="audio",
        storage_provider=storage.provider.__class__.__name__,
        mature=effective_mature,
    )
    if meta.get("duration_seconds") is not None:
        asset.duration_seconds = float(meta["duration_seconds"])
    await db.flush()

    await ensure_job_for_receipt(
        db,
        receipt=receipt,
        user_id=tenant_id,
        project_id=req.project_id or getattr(persona, "project_id", None),
        capability_id="audio.tts",
        provider_id=str(meta.get("provider") or "elevenlabs"),
        workflow_id="persona_speak",
        output_asset_id=asset.id,
        status_value="COMPLETED",
    )
    dag = LineageDAG(session=db)
    await dag.persist_depicts_edge(
        child_asset_id=asset.id,
        persona_id=persona.id,
        persona_version=persona.version,
        job_id=receipt.job_id,
        mature=effective_mature,
    )
    await db.commit()
    await db.refresh(asset)

    signed_url = generate_signed_url(storage_key, expiry_seconds=3600)
    audio_url = f"/v1/assets/{asset.id}/content?{signed_url.split('?', 1)[1]}"

    return {
        "status": "ok",
        "asset_id": asset.id,
        "audio_url": audio_url,
        "download_url": audio_url,
        "voice_used": meta.get("voice_id") or voice_id,
        "character_count": len(req.text),
        "persona_id": persona.id,
        "persona_version": persona.version,
        "mature": effective_mature,
        "content_mode": receipt.content_mode,
        "envelope_id": receipt.envelope.envelope_id,
        "warning": warning,
        "warnings": list(receipt.warnings),
        "metadata": meta,
    }
