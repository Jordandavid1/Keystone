'use strict';

/**
 * Edge-Level Personally Identifiable Information (PII) Scrubber
 * Redacts sensitive credentials, emails, phone numbers, and IP addresses
 * before payloads reach downstream processing, caching, or LLM context.
 */

class EdgePiiScrubber {
  /**
   * Scrubs raw content for PII while preserving technical tokens and valid JSON syntax.
   * @param {string|any} content Raw string or payload
   * @returns {string|any} Scrubbed string with sensitive PII replaced
   */
  scrub(content) {
    if (content === null || content === undefined) return content;
    if (typeof content !== 'string') return String(content);

    let result = content;

    // Email scrubbing (standard email addresses)
    result = result.replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[REDACTED_EMAIL]');

    // Obfuscated email scrubbing (e.g., user [at] domain [dot] com)
    result = result.replace(/[a-zA-Z0-9._%+-]+\s*\[at\]\s*[a-zA-Z0-9.-]+\s*\[dot\]\s*[a-zA-Z]{2,}/gi, '[REDACTED_EMAIL]');

    // Phone numbers (US & international with formatting delimiters)
    result = result.replace(/(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}/g, (match) => {
      // Guard: Avoid matching non-phone digit sequences (e.g. 1080x720, year 2026, version numbers)
      if (match.length >= 7 && (match.includes('-') || match.includes('.') || match.includes(' '))) {
        return '[REDACTED_PHONE]';
      }
      return match;
    });

    // Bearer / API keys (e.g., Hugging Face hf_..., OpenAI sk-..., or HTTP Authorization headers)
    result = result.replace(/(hf_[a-zA-Z0-9]{32,}|sk-[a-zA-Z0-9]{32,}|Bearer\s+[a-zA-Z0-9._-]{20,})/gi, '[REDACTED_KEY]');

    // IPv4 addresses (excluding localhost 127.0.0.1)
    result = result.replace(/\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/g, (match) => {
      if (match === '127.0.0.1') return match;
      return '[REDACTED_IP]';
    });

    return result;
  }
}

module.exports = { EdgePiiScrubber };
