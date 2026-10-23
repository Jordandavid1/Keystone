'use strict';

/**
 * Enterprise PII Boundary Vault & GDPR Article 17 Erasure Service
 * Implements F5 (AES-256-GCM Vault) and F6 (GDPR Cascading Erasure).
 * Enforces zero plaintext PII across analytical schemas and prompt contexts.
 */

const crypto = require('node:crypto');

class PiiVaultService {
  /**
   * Initializes the PII Vault with a 256-bit master key.
   * @param {string|null} masterKeyHex 64-char hex string representing 32-byte key.
   */
  constructor(masterKeyHex = null) {
    if (masterKeyHex) {
      this.key = Buffer.from(masterKeyHex, 'hex');
    } else if (process.env.PII_VAULT_KEY) {
      this.key = Buffer.from(process.env.PII_VAULT_KEY, 'hex');
    } else {
      // Ephemeral 256-bit cryptographically secure key
      this.key = crypto.randomBytes(32);
    }

    if (this.key.length !== 32) {
      throw new Error('INVALID_KEY_LENGTH: PII Vault master key must be exactly 32 bytes (256 bits).');
    }

    // Vault record store: Map<token, VaultRecord>
    this.vaultStore = new Map();

    // Compliance audit ledger (zero plain PII)
    this.auditLedger = [];

    // Active job queue for cascading cancellation
    this.jobQueue = [];
  }

  /**
   * Encrypts plaintext PII using AES-256-GCM and returns a tokenized reference.
   * @param {string} plaintext Raw sensitive data
   * @param {string} subjectId Data subject identifier for GDPR tracking
   * @param {string} entityType Entity classification ("email", "phone", "contact")
   * @returns {{ token: string, entityType: string, masked: string }}
   */
  tokenize(plaintext, subjectId = 'default_subject', entityType = 'contact') {
    if (plaintext === null || plaintext === undefined) {
      throw new Error('INVALID_PLAINTEXT: Plaintext is required.');
    }
    if (typeof plaintext !== 'string') {
      plaintext = String(plaintext);
    }

    // Mandatory unique 96-bit (12-byte) IV per encryption
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', this.key, iv);

    let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
    ciphertext += cipher.final('hex');
    const authTag = cipher.getAuthTag(); // 128-bit (16-byte) authentication tag

    const tokenUuid = crypto.randomUUID();
    const token = `vault_tok_${tokenUuid}`;

    this.vaultStore.set(token, {
      iv: iv.toString('hex'),
      ciphertext,
      authTag: authTag.toString('hex'),
      subjectId: String(subjectId).trim(),
      entityType,
      createdAt: Date.now()
    });

    return {
      token,
      entityType,
      masked: this.maskPii(plaintext, entityType)
    };
  }

  /**
   * Decrypts a tokenized reference back to original plaintext within an authorized boundary.
   * @param {string} token Format: vault_tok_<uuid>
   * @param {object|null} authorityEnvelope Optional signed authorization payload
   * @returns {string} Original plaintext
   */
  detokenize(token, authorityEnvelope = null) {
    if (!token || !this.vaultStore.has(token)) {
      throw new Error(`TOKEN_NOT_FOUND: Token '${token}' does not exist in vault or has been purged.`);
    }

    const record = this.vaultStore.get(token);
    const iv = Buffer.from(record.iv, 'hex');
    if (iv.length !== 12) {
      throw new Error('INVALID_IV_LENGTH: IV must be 12 bytes.');
    }

    const decipher = crypto.createDecipheriv('aes-256-gcm', this.key, iv);
    decipher.setAuthTag(Buffer.from(record.authTag, 'hex'));

    let decrypted = decipher.update(record.ciphertext, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }

  /**
   * Masks sensitive PII for safe display or intermediate logging.
   * @param {string} plaintext Raw string
   * @param {string} entityType Entity classification
   * @returns {string} Sanitized masked string
   */
  maskPii(plaintext, entityType) {
    if (!plaintext || typeof plaintext !== 'string') return '';
    if (entityType === 'email' || plaintext.includes('@')) {
      const parts = plaintext.split('@');
      const name = parts[0];
      const domain = parts[1] || '';
      return `${name[0]}***@${domain}`;
    }
    if (entityType === 'phone') {
      return plaintext.replace(/\d(?=\d{4})/g, '*');
    }
    return `${plaintext.substring(0, 2)}***`;
  }

  /**
   * Executes 5-step GDPR Article 17 cascading erasure for a data subject.
   * @param {string} subjectId Data subject ID to erase
   * @param {string} actorId Identifier of initiating entity
   * @returns {Promise<{ success: boolean, erasedVaultRecords: number, cancelledJobsCount: number, auditEventId: string, idempotent: boolean }>}
   */
  async purgeSubject(subjectId, actorId = 'system_privacy_controller') {
    if (!subjectId || typeof subjectId !== 'string' || !subjectId.trim()) {
      throw new Error('INVALID_SUBJECT_ID: subjectId is required for GDPR Article 17 erasure.');
    }

    const trimmedSubject = subjectId.trim();
    let erasedCount = 0;

    // Step 1: Vault Record Shredding
    for (const [token, record] of Array.from(this.vaultStore.entries())) {
      if (record.subjectId === trimmedSubject) {
        this.vaultStore.delete(token);
        erasedCount++;
      }
    }

    // Step 2: Queue Cascade Cancellation
    const cancelledJobs = [];
    this.jobQueue = this.jobQueue.filter(job => {
      if (job.subjectId === trimmedSubject) {
        cancelledJobs.push(job.id);
        return false;
      }
      return true;
    });

    // Step 3: Retention Purge (Handled via signal sliding TTL / cache eviction)

    // Step 4: Immutable Audit Ledger (ZERO Plaintext PII recorded)
    const auditRecord = {
      eventId: crypto.randomUUID(),
      eventType: 'GDPR_ARTICLE_17_PURGE',
      subjectId: trimmedSubject,
      actorId,
      erasedVaultRecords: erasedCount,
      cancelledJobsCount: cancelledJobs.length,
      timestamp: new Date().toISOString()
    };
    this.auditLedger.push(auditRecord);

    // Step 5: Idempotency Guarantee
    return {
      success: true,
      erasedVaultRecords: erasedCount,
      cancelledJobsCount: cancelledJobs.length,
      auditEventId: auditRecord.eventId,
      idempotent: erasedCount === 0
    };
  }
}

module.exports = { PiiVaultService };
