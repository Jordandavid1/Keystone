"""apps/api/src/services/credits.py
ADR-005 / Bible v2 §21, §27 Immutable DB Billing Ledger Service.
Handles transactional credit operations: deposit, hold_for_job, settle_hold, release_hold.
Enforces the dual-rail rule:
  - Processor 'stripe' CANNOT be used for 'unrestricted' mode (raises ValueError / HTTPException 400).
  - Processor 'ccbill' or adult processor is required for unrestricted top-ups / usage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from apps.api.src.db.models import CreditAccount, CreditLedger, UsageRecord, User


def get_or_create_credit_account(db: Session, user_id: str) -> CreditAccount:
    """Get the credit account for a user, or create it if not present."""
    account = db.query(CreditAccount).filter(CreditAccount.user_id == user_id).first()
    if not account:
        account = CreditAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(account)
        db.flush()
    return account


def deposit(
    db: Session,
    *,
    user_id: str,
    amount: int,
    processor: str,
    content_mode: str = "sfw",
    idempotency_key: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> CreditLedger:
    """
    Deposit credits into user's account with strict dual-rail processor checking.
    Dual-rail invariant:
      - processor == 'stripe' is forbidden for unrestricted mode.
    """
    if amount <= 0:
        raise ValueError("Deposit amount must be positive")

    norm_mode = (content_mode or "sfw").lower().strip()
    norm_proc = (processor or "stripe").lower().strip()

    if norm_proc == "stripe" and norm_mode == "unrestricted":
        raise ValueError("DUAL_RAIL_VIOLATION: Stripe cannot process unrestricted / adult transactions")

    if idempotency_key:
        existing = (
            db.query(CreditLedger)
            .filter(CreditLedger.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    account = get_or_create_credit_account(db, user_id)
    account.balance = (account.balance or 0) + amount
    account.updated_at = datetime.now(timezone.utc)

    ledger_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="topup",
        amount=amount,
        processor=norm_proc,
        idempotency_key=idempotency_key,
        metadata_=metadata or {"content_mode": norm_mode},
        created_at=datetime.now(timezone.utc),
    )
    db.add(ledger_entry)
    db.flush()
    return ledger_entry


def hold_for_job(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    amount: int,
    content_mode: str = "sfw",
    processor: Optional[str] = None,
) -> CreditLedger:
    """Place a temporary hold on user credits prior to job execution."""
    if amount <= 0:
        raise ValueError("Hold amount must be positive")

    norm_mode = (content_mode or "sfw").lower().strip()
    norm_proc = (processor or ("ccbill" if norm_mode == "unrestricted" else "stripe")).lower().strip()

    if norm_proc == "stripe" and norm_mode == "unrestricted":
        raise ValueError("DUAL_RAIL_VIOLATION: Stripe cannot be used for unrestricted mode")

    account = get_or_create_credit_account(db, user_id)
    if (account.balance or 0) < amount:
        raise ValueError(f"INSUFFICIENT_CREDITS: Required {amount}, available {account.balance}")

    account.balance = (account.balance or 0) - amount
    account.updated_at = datetime.now(timezone.utc)

    hold_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="hold",
        amount=-amount,
        processor=norm_proc,
        job_id=job_id,
        metadata_={"content_mode": norm_mode, "hold_amount": amount},
        created_at=datetime.now(timezone.utc),
    )
    db.add(hold_entry)
    db.flush()
    return hold_entry


def settle_hold(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    actual_amount: int,
    capability_id: str = "image.generation",
    gpu_class: str = "T4",
    vram_minutes: float = 0.5,
    gpu_seconds: float = 30.0,
    evaluator_ms: int = 150,
) -> Tuple[CreditLedger, UsageRecord]:
    """Settle a previous hold into finalized usage and immutable ledger settlement."""
    account = get_or_create_credit_account(db, user_id)

    # Find the corresponding hold
    hold = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "hold",
        )
        .first()
    )
    held_amount = abs(hold.amount) if hold else actual_amount

    # If actual was less than held, refund the difference
    diff = held_amount - actual_amount
    if diff > 0:
        account.balance = (account.balance or 0) + diff
        account.updated_at = datetime.now(timezone.utc)
    elif diff < 0:
        # Extra usage
        account.balance = (account.balance or 0) - abs(diff)
        account.updated_at = datetime.now(timezone.utc)

    settle_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="settle",
        amount=-actual_amount,
        processor=hold.processor if hold else "stripe",
        job_id=job_id,
        metadata_={
            "actual_amount": actual_amount,
            "held_amount": held_amount,
            "refunded": max(0, diff),
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(settle_entry)

    usage = UsageRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        job_id=job_id,
        capability_id=capability_id,
        gpu_class=gpu_class,
        vram_minutes=vram_minutes,
        gpu_seconds=gpu_seconds,
        evaluator_ms=evaluator_ms,
        cost_units=actual_amount,
        created_at=datetime.now(timezone.utc),
    )
    db.add(usage)
    db.flush()

    return settle_entry, usage


def release_hold(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    reason: str = "job_failed",
) -> Optional[CreditLedger]:
    """Release a held amount completely back to the user's available balance."""
    hold = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "hold",
        )
        .first()
    )
    if not hold:
        return None

    held_amount = abs(hold.amount)
    account = get_or_create_credit_account(db, user_id)
    account.balance = (account.balance or 0) + held_amount
    account.updated_at = datetime.now(timezone.utc)

    release_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="release",
        amount=held_amount,
        processor=hold.processor,
        job_id=job_id,
        metadata_={"reason": reason, "released_amount": held_amount},
        created_at=datetime.now(timezone.utc),
    )
    db.add(release_entry)
    db.flush()
    return release_entry


def get_balance(db: Session, user_id: str) -> Dict[str, Any]:
    """Compute verified balance and transactions from the database."""
    account = get_or_create_credit_account(db, user_id)
    entries = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id)
        .order_by(CreditLedger.created_at.desc())
        .all()
    )
    holds = sum(abs(e.amount) for e in entries if e.entry_type == "hold")
    return {
        "user_id": user_id,
        "balance": account.balance or 0,
        "held": holds,
        "transaction_count": len(entries),
    }
