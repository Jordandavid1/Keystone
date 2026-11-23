# KEYSTONE Acceptable Use Policy

**Effective Date:** January 1, 2026  
**Last Updated:** November 23, 2026  
**Ownership:** Jordan Maxwell  

## 1. Dual-Mode Operation & Mandatory Lawful-Content Floor
KEYSTONE operates under two explicit content modes resolved at the authoritative Gate (`session -> project -> user -> sfw`):
- **SFW Mode (Default):** Standard mainstream register across Playbooks 1–13. Mature assets, mature personas, and Playbooks 14–16 are excluded from compilation and retrieval.
- **UNRESTRICTED Mode (18+ Age-Gated):** Unlocked strictly after Stage-1 attestation (`POST /v1/account/age-verification`) or Stage-2 card/adult-processor verification (`POST /v1/billing/webhooks/adult-processor`). Lawful adult content, mature themes, erotica, and fantasy/graphic fiction are permitted when requested by an age-verified user.

## 2. Non-Configurable Prohibited Content Floor
Regardless of mode (`sfw` or `unrestricted`), you may NEVER use KEYSTONE to generate, request, compile, or distribute:
- Child Sexual Abuse Material (CSAM) or sexualization of minors.
- Non-consensual intimate imagery (NCII) or unconsented sexual deepfakes of real identifiable persons.
- Actionable chemical, biological, radiological, or nuclear (CBRN) weapons, explosives, terrorism, or self-harm step-by-step instructions.
- Cyber-exploitation, ransomware, or intrusion payloads targeting critical infrastructure.

## 3. Enforcement, Floor Watchdog & Audit Logging
All requests pass through the deterministic Gate (`apps/api/src/services/gate.py`), Aikido structural `<untrusted_content>` containment, and `FloorWatchdog`. Floor violations return HTTP `422 LAWFUL_CONTENT_FLOOR_VIOLATION`, persist immutable `authority_decisions` and `audit_events` rows in PostgreSQL, and never reach worker dispatch.
