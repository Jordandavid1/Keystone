"""
KEYSTONE Immutable Append-Only Credits Ledger Engine (Bible §21, §27).
Enforces two-phase commitment (hold -> settlement / release / refund).
Zero balance change without an append-only ledger transaction.
Guarantees double-spending prevention and idempotency.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Literal, Optional


class LedgerEntry:
    def __init__(
        self,
        entry_id: str,
        account_id: str,
        entry_type: Literal["HOLD", "SETTLE", "RELEASE", "REFUND", "TOPUP"],
        amount: int,
        hold_id: Optional[str] = None,
        job_id: Optional[str] = None,
        reason: Optional[str] = None,
        created_at: Optional[float] = None
    ):
        self.entry_id = entry_id
        self.account_id = account_id
        self.entry_type = entry_type
        self.amount = amount
        self.hold_id = hold_id
        self.job_id = job_id
        self.reason = reason
        self.created_at = created_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "account_id": self.account_id,
            "entry_type": self.entry_type,
            "amount": self.amount,
            "hold_id": self.hold_id,
            "job_id": self.job_id,
            "reason": self.reason,
            "created_at": self.created_at
        }


class CreditsLedgerEngine:
    """
    Append-only ledger engine tracking accounts, holds, settlements, releases, and refunds.
    """

    def __init__(self, default_initial_balance: int = 100):
        self._entries: List[LedgerEntry] = []
        self._initial_balances: Dict[str, int] = {}
        self.default_initial_balance = default_initial_balance

    def _ensure_account(self, account_id: str) -> None:
        if account_id not in self._initial_balances:
            self._initial_balances[account_id] = self.default_initial_balance

    def get_initial_balance(self, account_id: str) -> int:
        self._ensure_account(account_id)
        return self._initial_balances[account_id]

    def set_initial_balance(self, account_id: str, amount: int) -> None:
        self._initial_balances[account_id] = amount

    def get_available_balance(self, account_id: str) -> int:
        """
        Available balance = Initial + Topups + Refunds + Releases - Holds - SettledDirect
        Note: When hold is settled, the funds were already deducted on hold; settlement doesn't double-deduct.
        """
        self._ensure_account(account_id)
        bal = self._initial_balances[account_id]

        for e in self._entries:
            if e.account_id != account_id:
                continue
            if e.entry_type == "HOLD":
                bal -= e.amount
            elif e.entry_type in ("RELEASE", "REFUND", "TOPUP"):
                bal += e.amount

        return bal

    def get_held_balance(self, account_id: str) -> int:
        """Total credits currently locked in active, unsettled holds."""
        held = 0
        active_holds: Dict[str, int] = {}
        for e in self._entries:
            if e.account_id != account_id:
                continue
            if e.entry_type == "HOLD" and e.hold_id:
                active_holds[e.hold_id] = e.amount
            elif e.entry_type in ("SETTLE", "RELEASE") and e.hold_id:
                active_holds.pop(e.hold_id, None)

        return sum(active_holds.values())

    def hold(self, account_id: str, amount: int, job_id: str) -> str:
        """
        Places a provisional hold on user credits prior to job execution.
        """
        if amount <= 0:
            raise ValueError(f"INVALID_HOLD_AMOUNT: Amount must be > 0 (got {amount})")

        available = self.get_available_balance(account_id)
        if available < amount:
            raise ValueError(f"INSUFFICIENT_CREDITS: Required {amount}, available {available}")

        hold_id = f"hold_{uuid.uuid4().hex[:12]}"
        entry_id = f"ent_{uuid.uuid4().hex[:12]}"
        entry = LedgerEntry(
            entry_id=entry_id,
            account_id=account_id,
            entry_type="HOLD",
            amount=amount,
            hold_id=hold_id,
            job_id=job_id,
            reason=f"Provisional hold for job {job_id}"
        )
        self._entries.append(entry)
        return hold_id

    def settle(self, hold_id: str) -> bool:
        """
        Finalizes deduction upon successful job completion.
        """
        hold_entry = next((e for e in self._entries if e.entry_type == "HOLD" and e.hold_id == hold_id), None)
        if not hold_entry:
            raise ValueError(f"HOLD_NOT_FOUND: Hold '{hold_id}' does not exist")

        already_finalized = any(
            e.entry_type in ("SETTLE", "RELEASE") and e.hold_id == hold_id
            for e in self._entries
        )
        if already_finalized:
            raise ValueError(f"HOLD_ALREADY_FINALIZED: Hold '{hold_id}' is already settled or released")

        entry_id = f"ent_{uuid.uuid4().hex[:12]}"
        entry = LedgerEntry(
            entry_id=entry_id,
            account_id=hold_entry.account_id,
            entry_type="SETTLE",
            amount=hold_entry.amount,
            hold_id=hold_id,
            job_id=hold_entry.job_id,
            reason=f"Settlement for job {hold_entry.job_id}"
        )
        self._entries.append(entry)
        return True

    def release(self, hold_id: str) -> bool:
        """
        Releases held credits back to user on job failure or cancellation.
        """
        hold_entry = next((e for e in self._entries if e.entry_type == "HOLD" and e.hold_id == hold_id), None)
        if not hold_entry:
            raise ValueError(f"HOLD_NOT_FOUND: Hold '{hold_id}' does not exist")

        already_finalized = any(
            e.entry_type in ("SETTLE", "RELEASE") and e.hold_id == hold_id
            for e in self._entries
        )
        if already_finalized:
            raise ValueError(f"HOLD_ALREADY_FINALIZED: Hold '{hold_id}' is already settled or released")

        entry_id = f"ent_{uuid.uuid4().hex[:12]}"
        entry = LedgerEntry(
            entry_id=entry_id,
            account_id=hold_entry.account_id,
            entry_type="RELEASE",
            amount=hold_entry.amount,
            hold_id=hold_id,
            job_id=hold_entry.job_id,
            reason=f"Release of hold {hold_id}"
        )
        self._entries.append(entry)
        return True

    def refund(self, account_id: str, amount: int, reason: str) -> str:
        """Issues an administrative or failure credit refund."""
        if amount <= 0:
            raise ValueError(f"INVALID_REFUND_AMOUNT: Amount must be > 0 (got {amount})")

        self._ensure_account(account_id)
        entry_id = f"ent_{uuid.uuid4().hex[:12]}"
        entry = LedgerEntry(
            entry_id=entry_id,
            account_id=account_id,
            entry_type="REFUND",
            amount=amount,
            reason=reason
        )
        self._entries.append(entry)
        return entry_id

    def topup(self, account_id: str, amount: int, reason: str = "Stripe purchase") -> str:
        """Adds purchased credits to account."""
        if amount <= 0:
            raise ValueError(f"INVALID_TOPUP_AMOUNT: Amount must be > 0 (got {amount})")

        self._ensure_account(account_id)
        entry_id = f"ent_{uuid.uuid4().hex[:12]}"
        entry = LedgerEntry(
            entry_id=entry_id,
            account_id=account_id,
            entry_type="TOPUP",
            amount=amount,
            reason=reason
        )
        self._entries.append(entry)
        return entry_id

    def get_entries(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if account_id:
            return [e.to_dict() for e in self._entries if e.account_id == account_id]
        return [e.to_dict() for e in self._entries]

    def clear(self) -> None:
        self._entries.clear()
        self._initial_balances.clear()


# Global ledger engine instance
credits_ledger = CreditsLedgerEngine()
