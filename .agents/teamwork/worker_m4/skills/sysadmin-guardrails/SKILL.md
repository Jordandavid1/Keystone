# Sysadmin Guardrails Skill Dump
Source: C:\Users\Lesia Eden\.gemini\config\skills\sysadmin-guardrails\SKILL.md

Core Methodology:
- Pre-flight checks before modifications (disk, existing services/packages).
- Confirmation required for destructive operations (rm -rf, shutdown, purge, registry edits, unreviewed remote scripts).
- Back up before editing system/config files.
- Non-interactive execution (sudo -n, apt-get -y, PowerShell -NonInteractive -NoProfile).
- Long-running commands handled properly; write idempotent scripts (safe to run twice, check before change, explicit LF line endings, quoted paths).
- Verify with concrete evidence; never log secrets.
