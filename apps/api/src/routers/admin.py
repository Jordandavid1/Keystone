"""
KEYSTONE Operator Admin Console & Telemetry Router (Bible §26).
Provides system health monitoring, worker telemetry, queue depths,
audit logs, and governance compliance inspection.
"""

from __future__ import annotations

import ctypes
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import CreditAccount
from apps.api.src.db.session import get_db
from services.harness.src.worker_bridge import worker_bridge
from services.authority.src.credits_ledger import credits_ledger
from services.authority.src.engine import authority_engine
from packages.security.secret_scanner import COPYRIGHT_STATEMENT

router = APIRouter(prefix="/v1/admin", tags=["Operator Admin Console"])


def _get_real_host_memory_bytes() -> Tuple[int, int]:
    """Queries the operating system for real host RAM (used_bytes, total_bytes)."""
    if os.name == "nt":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = int(stat.ullTotalPhys)
                used = max(0, total - int(stat.ullAvailPhys))
                return used, total
        except Exception:
            pass
    else:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                meminfo = {}
                for line in fh:
                    parts = line.split(":")
                    if len(parts) == 2:
                        meminfo[parts[0].strip()] = int(parts[1].strip().split()[0]) * 1024
                total = meminfo.get("MemTotal", 0)
                avail = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
                if total > 0:
                    return max(0, total - avail), total
        except Exception:
            pass
    return 0, 0


class SystemTelemetry(BaseModel):
    timestamp: float
    active_workers: int
    gpu_vram_utilization_pct: float
    host_ram_used_bytes: int
    host_ram_total_bytes: Optional[int] = None
    queue_depth: int
    avg_latency_ms: float
    active_jobs: int
    ledger_entries_count: int
    copyright: str


class AdminCreditTopupRequest(BaseModel):
    account_id: str = Field(..., min_length=1, description="Tenant user_id or account_id")
    amount: int = Field(..., gt=0, le=10000000, description="Credits to add")
    reason: Optional[str] = Field("Operator console manual credit grant", description="Audit reason")


@router.get(
    "/telemetry",
    response_model=SystemTelemetry,
    summary="Get System & Worker Telemetry",
    description="Returns aggregate real-time hardware telemetry and worker pool metrics per Bible §26."
)
def get_system_telemetry() -> SystemTelemetry:
    workers = worker_bridge.list_workers(active_only=True)
    active_worker_count = len(workers)

    total_active_jobs = sum(int(w.get("metrics", {}).get("active_jobs", 0)) for w in workers)
    vram_samples = [
        float(w.get("metrics", {}).get("gpu_utilization_pct", w.get("metrics", {}).get("gpu_utilization", 0.0)))
        for w in workers
        if w.get("metrics")
    ]
    avg_vram = round(sum(vram_samples) / len(vram_samples), 1) if vram_samples else 0.0

    latency_samples = [
        float(w.get("metrics", {}).get("latency_ms", 0.0))
        for w in workers
        if w.get("metrics") and w.get("metrics", {}).get("latency_ms") is not None
    ]
    avg_latency = round(sum(latency_samples) / len(latency_samples), 1) if latency_samples else 0.0

    used_ram_bytes, total_ram_bytes = _get_real_host_memory_bytes()

    return SystemTelemetry(
        timestamp=time.time(),
        active_workers=active_worker_count,
        gpu_vram_utilization_pct=avg_vram,
        host_ram_used_bytes=used_ram_bytes,
        host_ram_total_bytes=total_ram_bytes,
        queue_depth=max(0, total_active_jobs),
        avg_latency_ms=avg_latency,
        active_jobs=total_active_jobs,
        ledger_entries_count=len(credits_ledger.get_entries()),
        copyright=COPYRIGHT_STATEMENT
    )


@router.get(
    "/audit/logs",
    summary="List Operational Audit Logs",
    description="Returns immutable system event, authority decision, and ledger audit trails."
)
def get_audit_logs(limit: int = Query(50, ge=1, le=500)) -> List[Dict[str, Any]]:
    logs: List[Dict[str, Any]] = []
    for e in credits_ledger.get_entries()[-limit:]:
        logs.append({
            "event_id": e.get("entry_id"),
            "category": "LEDGER_TRANSACTION",
            "action": e.get("entry_type"),
            "actor": e.get("account_id"),
            "amount": e.get("amount"),
            "timestamp": e.get("created_at"),
            "details": e.get("reason")
        })
    for a in authority_engine.audit_log[-limit:]:
        data = a.get("data", {})
        logs.append({
            "event_id": a.get("id"),
            "category": "AUTHORITY_DECISION",
            "action": f"{data.get('decision', 'EVAL')} ({data.get('capability_id', '')})",
            "actor": a.get("actor_id"),
            "amount": data.get("required_credits", 0),
            "timestamp": a.get("created_at"),
            "details": ", ".join(data.get("reason_codes", []))
        })
    return logs[-limit:]


@router.post(
    "/credits/topup",
    summary="Grant Studio Credits to Tenant Account",
    description="Adds credits to both the append-only CreditsLedgerEngine and SQLite CreditAccount."
)
async def admin_topup_credits(
    req: AdminCreditTopupRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    new_ledger_bal = credits_ledger.topup(req.account_id, req.amount, reason=req.reason or "Admin grant")
    res = await db.execute(select(CreditAccount).where(CreditAccount.user_id == req.account_id))
    acct = res.scalar_one_or_none()
    if acct:
        acct.balance += req.amount
        await db.commit()
    return {
        "status": "ok",
        "account_id": req.account_id,
        "added_credits": req.amount,
        "available_balance": acct.balance if acct else new_ledger_bal,
    }


@router.post(
    "/workers/probe",
    summary="Force Immediate Live Probe of Configured Worker Tunnels",
    description="Triggers KaggleWorkerDaemon to register and probe live Cognition and ComfyUI tunnels."
)
def admin_probe_workers() -> Dict[str, Any]:
    from services.harness.src.kaggle_daemon import get_kaggle_daemon
    daemon = get_kaggle_daemon()
    daemon.register_workers_in_process()
    daemon.pulse_heartbeat()
    workers = worker_bridge.list_workers(active_only=False)
    return {
        "status": "ok",
        "worker_count": len(workers),
        "workers": workers,
    }


@router.get(
    "/legal/policies",
    summary="List Legal Documentation Policies",
    description="Returns the inventory of 10 commercial legal policies."
)
def list_legal_policies() -> Dict[str, Any]:
    # Resolve to repository root / docs / legal
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    docs_dir = os.path.join(repo_root, "docs", "legal")
    policies = []
    if os.path.exists(docs_dir):
        for fname in sorted(os.listdir(docs_dir)):
            if fname.endswith(".md"):
                policies.append(fname)

    return {
        "status": "ok",
        "policy_count": len(policies),
        "policies": policies
    }
