# KEYSTONE Data Retention and Deletion Policy

**Effective Date:** January 1, 2026  
**Ownership:** Jordan Maxwell  

## 1. Asset Retention Windows
- **Active Workspace Assets:** Retained indefinitely while the account remains active and within quota limits.
- **Signed Download URLs:** 15-minute short-expiry URLs generated on demand.
- **Temporary Worker Artifacts:** Ephemeral worker scratch data purged automatically upon job completion.
- **Execution Logs & Audits:** Retained for 90 days for forensic security and SLA compliance.

## 2. User-Initiated Erasure (GDPR Art. 17)
Upon receiving an erasure request:
1. User account and credentials deleted immediately.
2. Projects, sessions, messages, and prompt history cascaded to deletion.
3. Media assets purged from Cloud Storage.
4. PII Vault token mapping entries shredded.
5. Financial ledger transactions retained in anonymized format to satisfy statutory accounting regulations.
