"""
Migration & SQLite to PostgreSQL ETL Script (Bible v2 §21; ADR-005 PR1).
Carries the 10 populated tables from artifacts/keystone-v1-final.sqlite to PostgreSQL,
asserts per-table row parity, and executes cleanly.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row

POSTGRES_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://keystone:keystone_test_password@localhost:5432/keystone_test"
)
SQLITE_ARCHIVE_PATH = Path("artifacts/keystone-v1-final.sqlite")

CARRIED_TABLES = [
    "users",
    "projects",
    "sessions",
    "messages",
    "assets",
    "requests",
    "jobs",
    "asset_relationships",
    "credit_accounts",
    "authority_decisions",
]


def migrate_sqlite_to_postgres(sqlite_path: Path = SQLITE_ARCHIVE_PATH, pg_url: str = POSTGRES_URL) -> Dict[str, int]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite archive not found at {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    parity_report = {}

    with psycopg.connect(pg_url) as pg_conn:
        with pg_conn.cursor() as pg_cur:
            # 1. Truncate in reverse FK order
            for table in reversed(CARRIED_TABLES):
                pg_cur.execute(f"TRUNCATE TABLE {table} CASCADE;")

            # 2. Migrate each table
            for table in CARRIED_TABLES:
                sqlite_cur.execute(f"SELECT * FROM {table}")
                rows = [dict(r) for r in sqlite_cur.fetchall()]
                count = len(rows)

                if count == 0:
                    parity_report[table] = 0
                    continue

                if table == "users":
                    for r in rows:
                        params = dict(r)
                        params["age_verified"] = bool(params.get("age_verified"))
                        params["role"] = params.get("role") or "user"
                        params["content_mode"] = params.get("content_mode") or "sfw"
                        pg_cur.execute(
                            """
                            INSERT INTO users (id, email, password_hash, role, content_mode, age_verified, is_active, is_suspended, created_at, updated_at)
                            VALUES (%(id)s, %(email)s, %(password_hash)s, %(role)s, %(content_mode)s, %(age_verified)s, TRUE, FALSE, %(created_at)s, %(updated_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                elif table == "projects":
                    for r in rows:
                        pg_cur.execute(
                            """
                            INSERT INTO projects (id, user_id, name, description, content_mode, deleted_at, created_at, updated_at)
                            VALUES (%(id)s, %(user_id)s, %(name)s, %(description)s, 'sfw', NULL, %(created_at)s, %(updated_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            r
                        )

                elif table == "sessions":
                    for r in rows:
                        pg_cur.execute(
                            """
                            INSERT INTO sessions (id, user_id, project_id, title, content_mode, created_at, updated_at)
                            VALUES (%(id)s, %(user_id)s, %(project_id)s, %(title)s, 'sfw', %(created_at)s, %(updated_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            r
                        )

                elif table == "messages":
                    for r in rows:
                        params = dict(r)
                        session_id = params["session_id"]
                        sqlite_cur.execute("SELECT user_id FROM sessions WHERE id = ?", (session_id,))
                        sess_row = sqlite_cur.fetchone()
                        params["user_id"] = sess_row[0] if sess_row else None
                        pg_cur.execute(
                            """
                            INSERT INTO messages (id, session_id, user_id, role, content, created_at)
                            VALUES (%(id)s, %(session_id)s, %(user_id)s, %(role)s, %(content)s, %(created_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                elif table == "assets":
                    for r in rows:
                        params = dict(r)
                        params["user_id"] = params.get("user_id") or params.get("owner_id")
                        params["asset_type"] = params.get("asset_type") or params.get("media_type") or "image"
                        params["size_bytes"] = params.get("size_bytes") or params.get("byte_size")
                        params.setdefault("filename", None)
                        params.setdefault("width", None)
                        params.setdefault("height", None)
                        params.setdefault("duration_seconds", None)
                        params.setdefault("checksum", None)
                        pg_cur.execute(
                            """
                            INSERT INTO assets (id, user_id, project_id, asset_type, storage_key, filename, mime_type, size_bytes, width, height, duration_seconds, checksum, mature, created_at, updated_at)
                            VALUES (%(id)s, %(user_id)s, %(project_id)s, %(asset_type)s, %(storage_key)s, %(filename)s, %(mime_type)s, %(size_bytes)s, %(width)s, %(height)s, %(duration_seconds)s, %(checksum)s, FALSE, %(created_at)s, %(created_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                elif table == "requests":
                    for r in rows:
                        params = dict(r)
                        params["intent_hint"] = params.get("request_text")
                        params["status"] = params.get("state")
                        params["project_id"] = None
                        pg_cur.execute(
                            """
                            INSERT INTO requests (id, user_id, project_id, session_id, intent_hint, status, created_at, completed_at)
                            VALUES (%(id)s, %(user_id)s, %(project_id)s, %(session_id)s, %(intent_hint)s, %(status)s, %(created_at)s, %(completed_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                elif table == "jobs":
                    for r in rows:
                        params = dict(r)
                        params["status"] = params.get("state") or "CREATED"
                        params["priority"] = params.get("priority") or 5
                        params["project_id"] = None
                        outputs_val = r.get("outputs") or "[]"
                        params["outputs_json"] = outputs_val if isinstance(outputs_val, str) else json.dumps(outputs_val)
                        params["failure_code"] = params.get("error_code")
                        params["queued_at"] = params.get("created_at")
                        params["started_at"] = params.get("created_at")
                        params["completed_at"] = params.get("updated_at")
                        pg_cur.execute(
                            """
                            INSERT INTO jobs (id, user_id, project_id, request_id, capability_id, provider_id, workflow_id, workflow_version, status, priority, outputs, failure_code, queued_at, started_at, completed_at, created_at, updated_at)
                            VALUES (%(id)s, %(user_id)s, %(project_id)s, %(request_id)s, %(capability_id)s, %(provider_id)s, %(workflow_id)s, %(workflow_version)s, %(status)s, %(priority)s, %(outputs_json)s::jsonb, %(failure_code)s, %(queued_at)s, %(started_at)s, %(completed_at)s, %(created_at)s, %(updated_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                elif table == "asset_relationships":
                    for r in rows:
                        pg_cur.execute(
                            """
                            INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type, job_id, persona_id, persona_version, created_at)
                            VALUES (%(id)s, %(parent_asset_id)s, %(child_asset_id)s, %(relationship_type)s, %(job_id)s, NULL, NULL, %(created_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            r
                        )

                elif table == "credit_accounts":
                    for r in rows:
                        pg_cur.execute(
                            """
                            INSERT INTO credit_accounts (id, user_id, balance, created_at, updated_at)
                            VALUES (%(id)s, %(user_id)s, %(balance)s, %(created_at)s, %(updated_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            r
                        )

                elif table == "authority_decisions":
                    for r in rows:
                        params = dict(r)
                        for json_field in ("sanitized_arguments", "reason_codes"):
                            val = params.get(json_field)
                            params[json_field + "_json"] = json.dumps(val) if val is not None else None
                        pg_cur.execute(
                            """
                            INSERT INTO authority_decisions (id, request_id, job_id, decision, capability_id, provider_id, sanitized_arguments, reason_codes, policy_bundle_version, capability_registry_version, harness_bundle_version, content_mode, floor_verdict, created_at)
                            VALUES (%(id)s, %(request_id)s, NULL, %(decision)s, %(capability_id)s, %(provider_id)s, %(sanitized_arguments_json)s::jsonb, %(reason_codes_json)s::jsonb, %(policy_bundle_version)s, %(capability_registry_version)s, %(harness_bundle_version)s, 'sfw', 'pass', %(created_at)s)
                            ON CONFLICT (id) DO NOTHING;
                            """,
                            params
                        )

                # Verify row count parity
                pg_cur.execute(f"SELECT count(*) FROM {table}")
                pg_count = pg_cur.fetchone()[0]
                assert pg_count == count, f"Row parity mismatch on {table}: SQLite has {count}, Postgres has {pg_count}"
                parity_report[table] = pg_count

            pg_conn.commit()

    return parity_report


if __name__ == "__main__":
    report = migrate_sqlite_to_postgres()
    print("ETL completed successfully with row parity:")
    for tbl, cnt in report.items():
        print(f"  {tbl}: {cnt} rows")
