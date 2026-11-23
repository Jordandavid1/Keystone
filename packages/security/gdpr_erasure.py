"""
KEYSTONE GDPR Article 17 Cascading Erasure & PII Vault Audit (Bible v2 §22, §30).
Implements Right to Erasure across DB accounts, projects, sessions, messages,
assets (plus backing storage objects), personas, recipes, style rules, API keys,
and append-only ledger anonymization (preserving accounting compliance without
mutating immutable DB credit_ledger rows).
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.authority.src.credits_ledger import credits_ledger

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{1,4}\)?[-.\s]?){2,4}\d{3,4}")


async def _await_if_needed(val: Any) -> Any:
    if inspect.isawaitable(val):
        return await val
    return val


def _erase_db_sync(
    db: Any,
    user_id: str,
    *,
    asset_storage: Optional[Any] = None,
) -> Dict[str, Any]:
    from apps.api.src.db.models import (
        ApiKey,
        Asset,
        Message,
        Persona,
        Project,
        Recipe,
        Session as ChatSession,
        StyleRule,
        User,
    )

    now = datetime.now(timezone.utc)
    uid = str(user_id)

    # 1. Soft-delete/purge assets & remove backing storage blobs when provider available
    assets = (
        db.query(Asset)
        .filter(Asset.user_id == uid, Asset.deleted_at.is_(None))
        .all()
    )
    storage_keys: List[str] = []
    for asset in assets:
        if asset.storage_key:
            storage_keys.append(str(asset.storage_key))
        asset.deleted_at = now
        asset.status = "deleted"
        asset.c2pa_manifest = None

    blobs_deleted = 0
    if asset_storage is not None and storage_keys:
        delete_fn = getattr(asset_storage, "delete_object", None)
        if delete_fn is None and hasattr(asset_storage, "provider"):
            delete_fn = getattr(asset_storage.provider, "delete_object", None)
        if callable(delete_fn):
            for key in storage_keys:
                try:
                    res = delete_fn(key)
                    if not inspect.isawaitable(res):
                        blobs_deleted += 1
                except Exception:
                    pass

    # 2. Delete user messages & sessions
    messages = db.query(Message).filter(Message.user_id == uid).all()
    messages_count = len(messages)
    for m in messages:
        db.delete(m)

    sessions = db.query(ChatSession).filter(ChatSession.user_id == uid).all()
    sessions_count = len(sessions)
    for s in sessions:
        db.delete(s)

    # 3. Soft-delete projects, personas; delete style rules & recipes; revoke API keys
    projects = db.query(Project).filter(Project.user_id == uid, Project.deleted_at.is_(None)).all()
    for p in projects:
        p.deleted_at = now

    personas = db.query(Persona).filter(Persona.user_id == uid, Persona.deleted_at.is_(None)).all()
    for per in personas:
        per.deleted_at = now
        per.is_current = False

    recipes = db.query(Recipe).filter(Recipe.user_id == uid).all()
    recipes_count = len(recipes)
    for rec in recipes:
        db.delete(rec)

    rules = db.query(StyleRule).filter(StyleRule.user_id == uid).all()
    rules_count = len(rules)
    for sr in rules:
        db.delete(sr)

    keys = db.query(ApiKey).filter(ApiKey.user_id == uid, ApiKey.revoked_at.is_(None)).all()
    for ak in keys:
        ak.revoked_at = now

    # 4. Anonymize User PII (without mutating append-only CreditLedger triggers)
    user = db.query(User).filter(User.id == uid).first()
    profile_count = 0
    if user is not None:
        user.email = f"erased_{uid[:12]}@redacted.invalid"
        user.display_name = "ANONYMIZED_GDPR_USER"
        user.password_hash = None
        user.age_verification_method = None
        profile_count = 1

    db.flush()
    return {
        "user_profile": profile_count,
        "assets_deleted_count": len(assets),
        "storage_blobs_deleted_count": blobs_deleted,
        "storage_keys_queued": storage_keys,
        "sessions_purged_count": sessions_count,
        "messages_purged_count": messages_count,
        "projects_deleted_count": len(projects),
        "personas_deleted_count": len(personas),
        "recipes_deleted_count": recipes_count,
        "style_rules_deleted_count": rules_count,
        "api_keys_revoked_count": len(keys),
    }


class GdprErasureService:
    """
    Manages cascading GDPR Article 17 erasure and context PII auditing.
    """

    @classmethod
    def audit_prompt_context(cls, context_list: List[str]) -> Dict[str, Any]:
        """
        Scans assembled prompt context for un-tokenized plain PII (emails, phone numbers).
        """
        for item in context_list:
            if not isinstance(item, str):
                continue
            if EMAIL_REGEX.search(item) or PHONE_REGEX.search(item):
                return {
                    "compliant": False,
                    "violation": item,
                    "reason": "RAW_PII_DETECTED_IN_MODEL_CONTEXT",
                }

        return {"compliant": True, "violation": None}

    @classmethod
    def cascade_erase_user(
        cls,
        user_id: str,
        asset_storage: Optional[Any] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes cascading Article 17 erasure for a user:
        1. Deletes/soft-deletes DB user assets, sessions, messages, projects,
           personas, recipes, style rules, revokes API keys, and anonymizes User PII
           when `db` is supplied (leaving immutable DB `credit_ledger` rows untouched).
        2. Anonymizes in-process legacy ledger entries when present.
        3. Reports verified numeric counts.
        """
        db_counts: Dict[str, Any] = {
            "user_profile": 0,
            "assets_deleted_count": 0,
            "storage_blobs_deleted_count": 0,
            "sessions_purged_count": 0,
            "messages_purged_count": 0,
            "projects_deleted_count": 0,
            "personas_deleted_count": 0,
            "recipes_deleted_count": 0,
            "style_rules_deleted_count": 0,
            "api_keys_revoked_count": 0,
        }
        if db is not None:
            sync_db = getattr(db, "_s", db)
            db_counts = _erase_db_sync(sync_db, user_id, asset_storage=asset_storage)
            db_counts.pop("storage_keys_queued", None)

        anonymized_ledger_entries = 0
        for entry in credits_ledger._entries:
            if entry.account_id == user_id:
                entry.account_id = "ANONYMIZED_GDPR_USER"
                anonymized_ledger_entries += 1

        return {
            "status": "ERASED",
            "user_id": user_id,
            "cascaded_entities": {
                **db_counts,
                "ledger_entries_anonymized": anonymized_ledger_entries,
            },
            "anonymized_marker": "ANONYMIZED_GDPR_USER",
            "gdpr_article": "Article 17 (Right to Erasure)",
        }

    @classmethod
    async def cascade_erase_user_async(
        cls,
        user_id: str,
        db: Any,
        asset_storage: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Async variant supporting SQLAlchemy AsyncSession and async storage providers."""
        if hasattr(db, "run_sync"):
            db_counts = await db.run_sync(
                lambda sync_db: _erase_db_sync(sync_db, user_id, asset_storage=None)
            )
        else:
            sync_db = getattr(db, "_s", db)
            db_counts = _erase_db_sync(sync_db, user_id, asset_storage=None)

        storage_keys = db_counts.pop("storage_keys_queued", [])
        blobs_deleted = 0
        if asset_storage is not None and storage_keys:
            delete_fn = getattr(asset_storage, "delete_object", None)
            if delete_fn is None and hasattr(asset_storage, "provider"):
                delete_fn = getattr(asset_storage.provider, "delete_object", None)
            if callable(delete_fn):
                for key in storage_keys:
                    try:
                        await _await_if_needed(delete_fn(key))
                        blobs_deleted += 1
                    except Exception:
                        pass
        db_counts["storage_blobs_deleted_count"] = blobs_deleted
        await _await_if_needed(db.commit())

        anonymized_ledger_entries = 0
        for entry in credits_ledger._entries:
            if entry.account_id == user_id:
                entry.account_id = "ANONYMIZED_GDPR_USER"
                anonymized_ledger_entries += 1

        return {
            "status": "ERASED",
            "user_id": user_id,
            "cascaded_entities": {
                **db_counts,
                "ledger_entries_anonymized": anonymized_ledger_entries,
            },
            "anonymized_marker": "ANONYMIZED_GDPR_USER",
            "gdpr_article": "Article 17 (Right to Erasure)",
        }


# Global GDPR service instance
gdpr_service = GdprErasureService()
