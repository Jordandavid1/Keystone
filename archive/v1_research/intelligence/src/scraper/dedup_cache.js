'use strict';

/**
 * SHA-256 Signal Deduplication Cache
 * Provides deterministic hashing across normalized URLs and canonicalized JSON payloads,
 * with a sliding 30-day TTL cache for real-time deduplication.
 */

const crypto = require('node:crypto');

class SignalDeduplicator {
  /**
   * Initializes the deduplicator with sliding TTL window.
   * @param {number} slidingTtlDays Time-to-live in days (default: 30)
   */
  constructor(slidingTtlDays = 30) {
    this.slidingTtlMs = slidingTtlDays * 24 * 60 * 60 * 1000;
    this.cache = new Map(); // hash -> { timestamp, createdAt, data }
  }

  /**
   * Normalizes URLs by lowercasing hostname, sorting query parameters, and stripping trailing slashes.
   * @param {string} rawUrl 
   * @returns {string} Normalized canonical URL
   */
  normalizeUrl(rawUrl) {
    if (!rawUrl || typeof rawUrl !== 'string') return '';
    try {
      const parsed = new URL(rawUrl.trim().toLowerCase());
      // Re-sort query parameters deterministically
      const params = Array.from(parsed.searchParams.entries()).sort((a, b) => a[0].localeCompare(b[0]));
      parsed.search = new URLSearchParams(params).toString();
      let pathStr = parsed.pathname;
      if (pathStr.length > 1) {
        pathStr = pathStr.replace(/\/+$/, '') || '/';
      }
      parsed.pathname = pathStr;
      return parsed.toString();
    } catch {
      return rawUrl.trim().toLowerCase().replace(/\/+$/, '');
    }
  }

  /**
   * Canonicalizes payload by deterministically sorting object keys.
   * @param {any} payload 
   * @returns {string} Canonicalized JSON string representation
   */
  canonicalizePayload(payload) {
    if (payload === null || payload === undefined) return '';
    if (typeof payload !== 'object') return String(payload);

    if (Array.isArray(payload)) {
      return JSON.stringify(payload.map(item => this.canonicalizePayload(item)));
    }

    const sortedKeys = Object.keys(payload).sort();
    const sortedObj = {};
    for (const key of sortedKeys) {
      sortedObj[key] = payload[key];
    }
    return JSON.stringify(sortedObj);
  }

  /**
   * Computes a 64-character lowercase hex SHA-256 hash for a composite key.
   * @param {string} url Target URL
   * @param {string} entityType Classification entity type
   * @param {any} payload Data payload
   * @returns {string} SHA-256 hexadecimal hash
   */
  computeHash(url, entityType, payload) {
    const normUrl = this.normalizeUrl(url);
    const normPayload = this.canonicalizePayload(payload);
    const compositeKey = `${normUrl}:${entityType}:${normPayload}`;
    return crypto.createHash('sha256').update(compositeKey).digest('hex');
  }

  /**
   * Checks whether the signal exists in cache within the sliding TTL window;
   * if found, renews TTL and returns hit; otherwise records new entry.
   * @param {string} url 
   * @param {string} entityType 
   * @param {any} payload 
   * @param {object} extraData Additional metadata to store
   * @returns {{ deduplicated: boolean, signalHash: string, [key: string]: any }}
   */
  checkAndStore(url, entityType, payload, extraData = {}) {
    const hash = this.computeHash(url, entityType, payload);
    const now = Date.now();

    if (this.cache.has(hash)) {
      const entry = this.cache.get(hash);
      if (now - entry.timestamp < this.slidingTtlMs) {
        // Sliding TTL renewal on access
        entry.timestamp = now;
        return {
          deduplicated: true,
          signalHash: hash,
          cachedAt: entry.createdAt,
          ...entry.data
        };
      }
      // Expired entry
      this.cache.delete(hash);
    }

    // Cache miss - store new signal
    const record = {
      timestamp: now,
      createdAt: now,
      data: { ...extraData, url, entityType }
    };
    this.cache.set(hash, record);

    return {
      deduplicated: false,
      signalHash: hash,
      ...extraData
    };
  }
}

module.exports = { SignalDeduplicator };
