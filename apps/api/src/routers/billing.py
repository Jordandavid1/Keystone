"""
KEYSTONE Dual-Rail Billing & Immutable Ledger Router (Bible v2 §21, §27, §40; ADR-005 PR9).
Provides idempotent Stripe (SFW-only) and Adult Processor (Stage-2 age gate + UNRESTRICTED rail)
webhook processing with HMAC-SHA256 verification, DB-backed ledger queries, and balance audits.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.db.models import AuditEvent, CreditAccount, CreditLedger, User
from apps.api.src.db.session import get_db
from apps.api.src.services.credits import (
    deposit_async,
    get_balance_async,
    get_transactions_async,
)
from services.authority.src.credits_ledger import credits_ledger

router = APIRouter(prefix="/v1/billing", tags=["Billing & Credits"])

DEFAULT_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


async def _await_if_needed(val: Any) -> Any:
    if inspect.isawaitable(val):
        return await val
    return val


def _is_uuid(val: Optional[str]) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def _has_db_account_or_user(db: AsyncSession, user_id: str) -> bool:
    if not _is_uuid(user_id):
        return False
    res = await db.execute(select(User.id).where(User.id == str(user_id)))
    if res.scalar_one_or_none() is not None:
        return True
    acct_res = await db.execute(select(CreditAccount.id).where(CreditAccount.user_id == str(user_id)))
    return acct_res.scalar_one_or_none() is not None


class CheckoutSessionRequest(BaseModel):
    user_id: str = Field(..., description="Target user account UUID")
    tier: str = Field("pro", description="Credit package tier: starter (50), pro (250), enterprise (1000)")
    credits: Optional[int] = Field(None, description="Explicit credit quantity override")
    content_mode: str = Field("sfw", description="Billing mode scope ('sfw' or 'unrestricted')")


class WebhookResponse(BaseModel):
    status: str
    duplicate: bool = False
    event_type: Optional[str] = None
    user_id: Optional[str] = None
    credits_added: Optional[int] = None


class TopUpRequest(BaseModel):
    amount: int = Field(100, ge=10, le=10000, description="Credits to add")
    reason: Optional[str] = Field("Manual Studio Top-up", description="Reason for top-up")


class AdultProcessorWebhookRequest(BaseModel):
    event_id: Optional[str] = None
    user_id: str
    event_type: str = "card_verified"
    card_last4: Optional[str] = "4242"
    processor: str = "adult_rail"
    credits: Optional[int] = None


class BillingManager:
    """
    Manages Stripe webhook deduplication, signature checking, dual-rail scoping, and credit top-ups.
    """

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or DEFAULT_STRIPE_WEBHOOK_SECRET
        self.processed_events: set[str] = set()

    def verify_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        secret = self.secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if not secret or not signature_header:
            return False

        expected_raw_sig = hmac.new(
            secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(signature_header, expected_raw_sig):
            return True

        parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
        if "v1" in parts:
            v1_sig = parts["v1"].strip()
            if "t" in parts:
                try:
                    ts = int(parts["t"].strip())
                except ValueError:
                    return False
                if abs(time.time() - ts) > 300:
                    return False
                signed_payload = f"{ts}.".encode("utf-8") + raw_payload
                expected_ts_sig = hmac.new(
                    secret.encode("utf-8"),
                    signed_payload,
                    hashlib.sha256,
                ).hexdigest()
                if hmac.compare_digest(v1_sig, expected_ts_sig):
                    return True
            return hmac.compare_digest(v1_sig, expected_raw_sig)

        return False

    def process_event(self, raw_payload: bytes, signature_header: str) -> Dict[str, Any]:
        if not self.verify_signature(raw_payload, signature_header):
            raise ValueError("INVALID_STRIPE_SIGNATURE: Webhook signature verification failed")

        try:
            event = json.loads(raw_payload.decode("utf-8"))
        except Exception:
            raise ValueError("MALFORMED_WEBHOOK_JSON: Failed to parse event JSON")

        event_id = str(event.get("id", ""))
        if not event_id:
            raise ValueError("MISSING_EVENT_ID: Event must have an 'id'")

        if event_id in self.processed_events:
            return {
                "status": "ALREADY_PROCESSED",
                "duplicate": True,
                "event_id": event_id,
            }

        event_type = event.get("type", "")
        data_object = event.get("data", {}).get("object", {})
        metadata = data_object.get("metadata", {})
        content_mode = str(metadata.get("content_mode") or "sfw").lower().strip()
        if content_mode == "unrestricted":
            raise ValueError(
                "PROCESSOR_MODE_VIOLATION: Stripe cannot process unrestricted transactions"
            )

        user_id = metadata.get("user_id") or data_object.get("client_reference_id") or "user_stripe_default"
        credits_to_add = int(metadata.get("credits") or 100)

        if event_type in ("checkout.session.completed", "payment_intent.succeeded"):
            credits_ledger.topup(
                account_id=user_id,
                amount=credits_to_add,
                reason=f"Stripe event {event_id} ({event_type})",
            )

        self.processed_events.add(event_id)

        return {
            "status": "PROCESSED",
            "duplicate": False,
            "event_id": event_id,
            "event_type": event_type,
            "user_id": user_id,
            "credits_added": credits_to_add,
            "content_mode": content_mode,
        }

    def clear(self) -> None:
        self.processed_events.clear()


billing_manager = BillingManager()


def _verify_adult_processor_signature(raw_payload: bytes, signature_header: str) -> bool:
    secret = os.getenv("ADULT_PROCESSOR_WEBHOOK_SECRET", "").strip()
    if not secret or not signature_header:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_payload,
        hashlib.sha256,
    ).hexdigest()
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256="):].strip()
    return hmac.compare_digest(sig, expected)


@router.post(
    "/webhook",
    summary="Stripe Webhook Handler",
    description="Idempotently processes signed Stripe SFW-only billing events with HMAC-SHA256 verification.",
)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    raw_body = await request.body()
    try:
        result = billing_manager.process_event(raw_body, stripe_signature or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if result.get("status") == "PROCESSED" and result.get("credits_added"):
        uid = str(result.get("user_id") or "")
        if await _has_db_account_or_user(db, uid):
            await deposit_async(
                db,
                user_id=uid,
                amount=int(result["credits_added"]),
                processor="stripe",
                content_mode="sfw",
                idempotency_key=f"stripe:{result.get('event_id')}",
            )
            await _await_if_needed(db.commit())

    return result


@router.post(
    "/checkout/session",
    summary="Create Stripe Checkout Session",
    description="Initializes a test-mode Stripe checkout session for purchasing SFW credits.",
)
def create_checkout_session(
    req: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if str(req.content_mode).lower().strip() == "unrestricted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PROCESSOR_MODE_VIOLATION: Stripe checkout only supports SFW mode.",
        )
    tier_credits = {"starter": 50, "pro": 250, "enterprise": 1000}
    credit_qty = req.credits or tier_credits.get(req.tier.lower(), 100)
    session_id = f"cs_test_{uuid.uuid4().hex[:16]}"

    return {
        "session_id": session_id,
        "user_id": req.user_id,
        "credits": credit_qty,
        "tier": req.tier,
        "checkout_url": f"https://checkout.stripe.com/pay/{session_id}",
        "status": "open",
    }


@router.get(
    "/balance/{account_id}",
    summary="Get Account Credits Balance",
    description="Returns available balance, held balance, and ledger entries for user.",
)
async def get_account_balance(
    account_id: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if str(current_user.id) != account_id and getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot inspect another user's billing balance",
        )
    if await _has_db_account_or_user(db, account_id):
        return await get_balance_async(db, account_id)

    available = credits_ledger.get_available_balance(account_id)
    held = credits_ledger.get_held_balance(account_id)
    entries = credits_ledger.get_entries(account_id)
    return {
        "account_id": account_id,
        "balance": available,
        "available_credits": available,
        "held": held,
        "held_credits": held,
        "total_balance": available + held,
        "transaction_count": len(entries),
    }


@router.get(
    "/transactions/{account_id}",
    summary="List Ledger Transactions",
    description="Returns full append-only ledger transaction history for user account.",
)
async def get_account_transactions(
    account_id: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    if str(current_user.id) != account_id and getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot inspect another user's billing transactions",
        )
    if await _has_db_account_or_user(db, account_id):
        return await get_transactions_async(db, account_id)
    return credits_ledger.get_entries(account_id)


@router.get(
    "/balance",
    summary="Get Current Tenant Credits Balance",
    description="Returns available balance and hold for authenticated user.",
)
async def get_current_user_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    uid = str(current_user.id)
    if await _has_db_account_or_user(db, uid):
        return await get_balance_async(db, uid)

    available = credits_ledger.get_available_balance(uid)
    held = credits_ledger.get_held_balance(uid)
    entries = credits_ledger.get_entries(uid)
    return {
        "account_id": uid,
        "balance": available,
        "available_credits": available,
        "held": held,
        "held_credits": held,
        "total_balance": available + held,
        "transaction_count": len(entries),
    }


@router.get(
    "/transactions",
    summary="List Current Tenant Ledger Transactions",
    description="Returns transaction history for authenticated user.",
)
async def get_current_user_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    uid = str(current_user.id)
    if await _has_db_account_or_user(db, uid):
        return await get_transactions_async(db, uid)
    return credits_ledger.get_entries(uid)


@router.post(
    "/topup",
    summary="Top-up Account Credits",
    description="Dev/admin credit top-up (disabled for non-admin users in production).",
)
async def topup_current_user_credits(
    req: TopUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    if (
        os.getenv("KEYSTONE_ENV", "development").strip().lower() == "production"
        and getattr(current_user, "role", "user") != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SELF_TOPUP_DISABLED_IN_PRODUCTION",
        )

    uid = str(current_user.id)
    if await _has_db_account_or_user(db, uid):
        await deposit_async(
            db,
            user_id=uid,
            amount=req.amount,
            processor="internal",
            content_mode="sfw",
            metadata={"reason": req.reason or "Studio Top-up"},
        )
        await _await_if_needed(db.commit())
        return await get_balance_async(db, uid)

    credits_ledger.topup(account_id=uid, amount=req.amount, reason=req.reason or "Studio Top-up")
    available = credits_ledger.get_available_balance(uid)
    held = credits_ledger.get_held_balance(uid)
    return {
        "account_id": uid,
        "balance": available,
        "available_credits": available,
        "held": held,
        "held_credits": held,
        "total_balance": available + held,
        "transaction_count": len(credits_ledger.get_entries(uid)),
    }


@router.post(
    "/webhooks/adult-processor",
    summary="Adult Processor Webhook (Stage-2 Age Verification)",
    description="HMAC-SHA256 verified webhook confirming card/adult-processor Stage-2 age verification and unrestricted deposits.",
)
async def handle_adult_processor_webhook(
    request: Request,
    x_adult_processor_signature: Optional[str] = Header(None, alias="X-Adult-Processor-Signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    raw_body = await request.body()
    if not _verify_adult_processor_signature(raw_body, x_adult_processor_signature or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_ADULT_PROCESSOR_SIGNATURE",
        )

    try:
        raw_json = json.loads(raw_body.decode("utf-8"))
        payload = AdultProcessorWebhookRequest(**raw_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MALFORMED_ADULT_WEBHOOK_PAYLOAD: {exc}",
        )

    if payload.processor.lower().strip() == "stripe":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PROCESSOR_MODE_VIOLATION: Stripe cannot be used on the adult processor rail.",
        )

    user_res = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    idem_key = f"adult_rail:{payload.event_id}" if payload.event_id else None
    if payload.event_id:
        existing_ledger = await db.execute(
            select(CreditLedger).where(CreditLedger.idempotency_key == idem_key)
        )
        if existing_ledger.scalar_one_or_none() is not None:
            return {
                "status": "ALREADY_PROCESSED",
                "duplicate": True,
                "user_id": user.id,
                "age_verified": bool(user.age_verified),
                "method": user.age_verification_method,
            }
        audit_res = await db.execute(
            select(AuditEvent).where(
                AuditEvent.user_id == user.id,
                AuditEvent.event_type == "account.age_verified_stage2",
            )
        )
        for evt in audit_res.scalars().all():
            if isinstance(evt.payload, dict) and evt.payload.get("event_id") == payload.event_id:
                return {
                    "status": "ALREADY_PROCESSED",
                    "duplicate": True,
                    "user_id": user.id,
                    "age_verified": bool(user.age_verified),
                    "method": user.age_verification_method,
                }

    now = datetime.now(timezone.utc)
    user.age_verified = True
    user.age_verification_method = "card_adult_processor"
    user.age_verified_at = now

    audit = AuditEvent(
        id=str(uuid.uuid4()),
        user_id=user.id,
        event_type="account.age_verified_stage2",
        payload={
            "event_id": payload.event_id,
            "processor": payload.processor,
            "event_type": payload.event_type,
            "method": "card_adult_processor",
            "card_last4": payload.card_last4,
            "verified_at": now.isoformat(),
        },
    )
    db.add(audit)

    credits_added = 0
    if payload.credits and payload.credits > 0:
        await deposit_async(
            db,
            user_id=user.id,
            amount=int(payload.credits),
            processor=payload.processor,
            content_mode="unrestricted",
            idempotency_key=idem_key,
            metadata={
                "event_id": payload.event_id,
                "card_last4": payload.card_last4,
                "stage": "stage2_adult_processor",
            },
            age_verified_by_processor=True,
        )
        credits_added = int(payload.credits)

    await _await_if_needed(db.commit())
    return {
        "status": "success",
        "duplicate": False,
        "user_id": user.id,
        "age_verified": True,
        "method": user.age_verification_method,
        "processor": payload.processor,
        "credits_added": credits_added,
    }
