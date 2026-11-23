"""apps/api/src/services/credits.py
ADR-005 / Bible v2 §21, §27 Immutable DB Billing Ledger Service.
Handles transactional credit operations: deposit, hold_for_job, settle_hold, release_hold.
Enforces the dual-rail rule:
  - Processor 'stripe' CANNOT be used for 'unrestricted' mode (raises ValueError).
  - Processor 'adult_rail' / 'ccbill' / 'crypto' is required for unrestricted top-ups / usage.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from sqlalchemy.orm import Query, Session

from apps.api.src.db.models import CreditAccount, CreditLedger, UsageRecord, User

T = TypeVar("T")


def _maybe_for_update(query: Query[Any], db: Session) -> Query[Any]:
    """Apply SELECT ... FOR UPDATE on PostgreSQL; no-op on SQLite."""
    bind = getattr(db, "bind", None)
    dialect = getattr(bind, "dialect", None) if bind is not None else None
    if getattr(dialect, "name", "") == "postgresql":
        return query.with_for_update()
    return query


async def _run_sync(db: Any, fn: Callable[[Session], T]) -> T:
    """Execute a synchronous ORM callable against AsyncSession, _AsyncSessionAdapter, or sync Session."""
    if hasattr(db, "run_sync"):
        res = db.run_sync(fn)
        if inspect.isawaitable(res):
            return await res
        return res
    sync_session = getattr(db, "_s", db)
    return fn(sync_session)


def get_or_create_credit_account(db: Session, user_id: str, *, for_update: bool = False) -> CreditAccount:
    """Get the credit account for a user, or create it if not present."""
    q = db.query(CreditAccount).filter(CreditAccount.user_id == user_id)
    if for_update:
        q = _maybe_for_update(q, db)
    account = q.first()
    if not account:
        now = datetime.now(timezone.utc)
        account = CreditAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=0,
            created_at=now,
            updated_at=now,
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
    age_verified_by_processor: bool = False,
) -> CreditLedger:
    """
    Deposit credits into user's account with strict dual-rail processor & age verification checks.
    Dual-rail invariant:
      - processor == 'stripe' is forbidden for unrestricted mode.
    """
    if amount <= 0:
        raise ValueError("Deposit amount must be positive")

    norm_mode = (content_mode or "sfw").lower().strip()
    norm_proc = (processor or "stripe").lower().strip()

    if norm_proc == "stripe" and norm_mode == "unrestricted":
        raise ValueError(
            "PROCESSOR_MODE_VIOLATION (DUAL_RAIL_VIOLATION): Stripe cannot process unrestricted / adult transactions"
        )

    if norm_mode == "unrestricted" and not age_verified_by_processor:
        user_row = db.query(User).filter(User.id == user_id).first()
        if user_row is not None and not bool(getattr(user_row, "age_verified", False)):
            raise ValueError("AGE_VERIFICATION_REQUIRED: Unrestricted deposit requires age verification")

    if idempotency_key:
        existing = (
            db.query(CreditLedger)
            .filter(CreditLedger.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    account = get_or_create_credit_account(db, user_id, for_update=True)
    account.balance = (account.balance or 0) + int(amount)
    now = datetime.now(timezone.utc)
    account.updated_at = now

    meta = dict(metadata or {})
    meta.setdefault("content_mode", norm_mode)

    ledger_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="topup",
        amount=int(amount),
        processor=norm_proc,
        idempotency_key=idempotency_key,
        metadata_=meta,
        created_at=now,
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
    idempotency_key: Optional[str] = None,
) -> CreditLedger:
    """Place an idempotent temporary hold on user credits prior to job execution."""
    if amount <= 0:
        raise ValueError("Hold amount must be positive")

    norm_mode = (content_mode or "sfw").lower().strip()
    norm_proc = (processor or ("adult_rail" if norm_mode == "unrestricted" else "stripe")).lower().strip()

    if norm_proc == "stripe" and norm_mode == "unrestricted":
        raise ValueError(
            "PROCESSOR_MODE_VIOLATION (DUAL_RAIL_VIOLATION): Stripe cannot be used for unrestricted mode"
        )

    if idempotency_key:
        existing = (
            db.query(CreditLedger)
            .filter(CreditLedger.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    account = get_or_create_credit_account(db, user_id, for_update=True)
    if (account.balance or 0) < int(amount):
        raise ValueError(f"INSUFFICIENT_CREDITS: Required {amount}, available {account.balance}")

    account.balance = (account.balance or 0) - int(amount)
    now = datetime.now(timezone.utc)
    account.updated_at = now

    hold_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="hold",
        amount=-int(amount),
        processor=norm_proc,
        job_id=job_id,
        idempotency_key=idempotency_key,
        metadata_={"content_mode": norm_mode, "hold_amount": int(amount)},
        created_at=now,
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
    evaluator_ms: Optional[int] = None,
    eval_seconds: Optional[float] = None,
) -> Tuple[CreditLedger, UsageRecord]:
    """Settle a previous hold into finalized usage and immutable ledger settlement (idempotent)."""
    existing_settle = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "settle",
        )
        .first()
    )
    if existing_settle:
        existing_usage = (
            db.query(UsageRecord)
            .filter(UsageRecord.user_id == user_id, UsageRecord.job_id == job_id)
            .first()
        )
        if existing_usage is None:
            eff_ms = int(evaluator_ms) if evaluator_ms is not None else int((eval_seconds or 0.15) * 1000)
            existing_usage = UsageRecord(
                id=str(uuid.uuid4()),
                user_id=user_id,
                job_id=job_id,
                capability_id=capability_id,
                gpu_class=gpu_class,
                vram_minutes=vram_minutes,
                gpu_seconds=gpu_seconds,
                evaluator_ms=eff_ms,
                cost_units=actual_amount,
                created_at=datetime.now(timezone.utc),
            )
            db.add(existing_usage)
            db.flush()
        return existing_settle, existing_usage

    existing_release = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "release",
        )
        .first()
    )
    if existing_release:
        raise ValueError("HOLD_ALREADY_FINALIZED: Hold was already released")

    account = get_or_create_credit_account(db, user_id, for_update=True)

    hold = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "hold",
        )
        .first()
    )
    held_amount = abs(hold.amount) if hold else 0

    now = datetime.now(timezone.utc)
    if hold is None:
        # Direct settlement without prior hold
        if (account.balance or 0) < int(actual_amount):
            raise ValueError(f"INSUFFICIENT_CREDITS: Required {actual_amount}, available {account.balance}")
        account.balance = (account.balance or 0) - int(actual_amount)
        account.updated_at = now
    else:
        diff = held_amount - int(actual_amount)
        if diff > 0:
            account.balance = (account.balance or 0) + diff
            account.updated_at = now
        elif diff < 0:
            account.balance = (account.balance or 0) - abs(diff)
            account.updated_at = now

    eff_eval_ms = (
        int(evaluator_ms)
        if evaluator_ms is not None
        else int(round(float(eval_seconds if eval_seconds is not None else 0.15) * 1000))
    )

    settle_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="settle",
        amount=-int(actual_amount),
        processor=hold.processor if hold else "stripe",
        job_id=job_id,
        idempotency_key=f"settle:{job_id}" if job_id else None,
        metadata_={
            "actual_amount": int(actual_amount),
            "held_amount": held_amount,
            "refunded": max(0, held_amount - int(actual_amount)) if hold else 0,
        },
        created_at=now,
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
        evaluator_ms=eff_eval_ms,
        cost_units=int(actual_amount),
        created_at=now,
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
    """Release an active held amount completely back to the user's available balance (idempotent)."""
    existing_settle = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "settle",
        )
        .first()
    )
    if existing_settle:
        return None

    existing_release = (
        db.query(CreditLedger)
        .filter(
            CreditLedger.user_id == user_id,
            CreditLedger.job_id == job_id,
            CreditLedger.entry_type == "release",
        )
        .first()
    )
    if existing_release:
        return existing_release

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
    now = datetime.now(timezone.utc)
    account = get_or_create_credit_account(db, user_id, for_update=True)
    account.balance = (account.balance or 0) + held_amount
    account.updated_at = now

    release_entry = CreditLedger(
        id=str(uuid.uuid4()),
        user_id=user_id,
        account_id=account.id,
        entry_type="release",
        amount=held_amount,
        processor=hold.processor,
        job_id=job_id,
        idempotency_key=f"release:{job_id}" if job_id else None,
        metadata_={"reason": reason, "released_amount": held_amount},
        created_at=now,
    )
    db.add(release_entry)
    db.flush()
    return release_entry


def get_balance(db: Session, user_id: str) -> Dict[str, Any]:
    """Compute verified available balance, active held credits, and transaction count from DB."""
    account = get_or_create_credit_account(db, user_id)
    entries = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id)
        .order_by(CreditLedger.created_at.desc())
        .all()
    )
    finalized_job_ids = {
        str(e.job_id)
        for e in entries
        if e.entry_type in ("settle", "release") and e.job_id is not None
    }
    active_held = sum(
        abs(int(e.amount))
        for e in entries
        if e.entry_type == "hold" and (e.job_id is None or str(e.job_id) not in finalized_job_ids)
    )
    available = int(account.balance or 0)
    return {
        "user_id": user_id,
        "account_id": user_id,
        "balance": available,
        "available_credits": available,
        "held": active_held,
        "held_credits": active_held,
        "total_balance": available + active_held,
        "transaction_count": len(entries),
    }


def get_transactions(db: Session, user_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    """Return DB append-only ledger transactions for a user."""
    entries = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "account_id": e.user_id,
            "credit_account_id": e.account_id,
            "entry_type": e.entry_type,
            "amount": int(e.amount),
            "processor": e.processor,
            "job_id": e.job_id,
            "idempotency_key": e.idempotency_key,
            "metadata": e.metadata_ or {},
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


async def deposit_async(db: Any, **kwargs: Any) -> CreditLedger:
    return await _run_sync(db, lambda sync_db: deposit(sync_db, **kwargs))


async def hold_for_job_async(db: Any, **kwargs: Any) -> CreditLedger:
    return await _run_sync(db, lambda sync_db: hold_for_job(sync_db, **kwargs))


async def settle_hold_async(db: Any, **kwargs: Any) -> Tuple[CreditLedger, UsageRecord]:
    return await _run_sync(db, lambda sync_db: settle_hold(sync_db, **kwargs))


async def release_hold_async(db: Any, **kwargs: Any) -> Optional[CreditLedger]:
    return await _run_sync(db, lambda sync_db: release_hold(sync_db, **kwargs))


async def get_balance_async(db: Any, user_id: str) -> Dict[str, Any]:
    return await _run_sync(db, lambda sync_db: get_balance(sync_db, user_id))


async def get_transactions_async(db: Any, user_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    return await _run_sync(db, lambda sync_db: get_transactions(sync_db, user_id, limit=limit))
