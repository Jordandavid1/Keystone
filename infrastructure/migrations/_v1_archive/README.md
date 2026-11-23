# Historical v1 Migrations Archive

The SQL files in this directory (`0001_core.sql` and `0002_keystone_full_schema.sql`) are frozen historical artifacts from Keystone Bible v1.

**DO NOT REUSE OR EXECUTE IN LIVE PATHS.**
`0001_core.sql` is incomplete (lacks `personas`, `projects.deleted_at`, and modern v2 columns).

All canonical database migrations are managed exclusively via Alembic starting with revision `0001_baseline_v2.py`.
