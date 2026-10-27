"""
KEYSTONE Stripe Test-Mode Billing & Ledger Router (Bible §27).
Provides idempotent webhook processing with HMAC-SHA256 signature verification,
credit checkout sessions, balance inspection, and ledger transaction audits.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from services.authority.src.credits_ledger import credits_ledger

router = APIRouter(prefix="/v1/billing", tags=["Billing & Credits"])

DEFAULT_STRIPE_WEBHOOK_SECRET = os.getenv(
    "STRIPE_WEBHOOK_SECRET",
    "whsec_test_keystone_stripe_webhook_secret_key"
)


class CheckoutSessionRequest(BaseModel):
    user_id: str = Field(..., description="Target user account UUID")
    tier: str = Field("pro", description="Credit package tier: starter (50), pro (250), enterprise (1000)")
    credits: Optional[int] = Field(None, description="Explicit credit quantity override")


class WebhookResponse(BaseModel):
    status: str
    duplicate: bool = False
    event_type: Optional[str] = None
    user_id: Optional[str] = None
    credits_added: Optional[int] = None


class BillingManager:
    """
    Manages Stripe webhook deduplication, signature checking, and credit top-ups.
    """

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or DEFAULT_STRIPE_WEBHOOK_SECRET
        self.processed_events: set[str] = set()

    def verify_signature(self, raw_payload: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        # Supports standard hex signature or t=...,v1=... format
        expected_sig = hmac.new(
            self.secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256
        ).hexdigest()

        if signature_header == expected_sig:
            return True

        # Check Stripe timestamped format: t=12345,v1=abc
        parts = dict(item.split("=") for item in signature_header.split(",") if "=" in item)
        if "v1" in parts:
            return hmac.compare_digest(parts["v1"], expected_sig)

        return hmac.compare_digest(signature_header, expected_sig)

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

        # Idempotency check: duplicate event
        if event_id in self.processed_events:
            return {
                "status": "ALREADY_PROCESSED",
                "duplicate": True,
                "event_id": event_id
            }

        event_type = event.get("type", "")
        data_object = event.get("data", {}).get("object", {})
        metadata = data_object.get("metadata", {})
        user_id = metadata.get("user_id") or data_object.get("client_reference_id") or "user_stripe_default"
        credits_to_add = int(metadata.get("credits") or 100)

        if event_type in ("checkout.session.completed", "payment_intent.succeeded"):
            credits_ledger.topup(
                account_id=user_id,
                amount=credits_to_add,
                reason=f"Stripe event {event_id} ({event_type})"
            )

        self.processed_events.add(event_id)

        return {
            "status": "PROCESSED",
            "duplicate": False,
            "event_type": event_type,
            "user_id": user_id,
            "credits_added": credits_to_add
        }

    def clear(self) -> None:
        self.processed_events.clear()


billing_manager = BillingManager()


@router.post(
    "/webhook",
    summary="Stripe Webhook Handler",
    description="Idempotently processes signed Stripe billing events with HMAC-SHA256 verification."
)
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
) -> Dict[str, Any]:
    raw_body = await request.body()
    try:
        result = billing_manager.process_event(raw_body, stripe_signature or "")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/checkout/session",
    summary="Create Stripe Checkout Session",
    description="Initializes a test-mode Stripe checkout session for purchasing credits."
)
def create_checkout_session(req: CheckoutSessionRequest) -> Dict[str, Any]:
    tier_credits = {"starter": 50, "pro": 250, "enterprise": 1000}
    credit_qty = req.credits or tier_credits.get(req.tier.lower(), 100)
    session_id = f"cs_test_{uuid.uuid4().hex[:16]}"

    return {
        "session_id": session_id,
        "user_id": req.user_id,
        "credits": credit_qty,
        "tier": req.tier,
        "checkout_url": f"https://checkout.stripe.com/pay/{session_id}",
        "status": "open"
    }


@router.get(
    "/balance/{account_id}",
    summary="Get Account Credits Balance",
    description="Returns available balance, held balance, and ledger entries for user."
)
def get_account_balance(account_id: str) -> Dict[str, Any]:
    available = credits_ledger.get_available_balance(account_id)
    held = credits_ledger.get_held_balance(account_id)
    entries = credits_ledger.get_entries(account_id)

    return {
        "account_id": account_id,
        "available_credits": available,
        "held_credits": held,
        "total_balance": available + held,
        "transaction_count": len(entries)
    }


@router.get(
    "/transactions/{account_id}",
    summary="List Ledger Transactions",
    description="Returns full append-only ledger transaction history for user account."
)
def get_account_transactions(account_id: str) -> List[Dict[str, Any]]:
    return credits_ledger.get_entries(account_id)
