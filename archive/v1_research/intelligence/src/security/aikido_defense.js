'use strict';

/**
 * Aikido Prompt-Injection Defense Service
 * Neutralizes adversarial prompt injections and delimiter escapes embedded in
 * scraped external web content, UI descriptions, and user inputs.
 */

class AikidoDefenseService {
  /**
   * Quarantines untrusted external content inside <untrusted_content> structural delimiters.
   * @param {string|null|undefined} content Raw untrusted input
   * @returns {string} Enclosed and escaped string
   */
  quarantine(content) {
    if (content === null || content === undefined) {
      return '<untrusted_content>\n</untrusted_content>';
    }
    const str = String(content);
    if (str === '') {
      return '<untrusted_content>\n\n</untrusted_content>';
    }
    const sanitized = this.escapeDelimiters(str);
    return `<untrusted_content>\n${sanitized}\n</untrusted_content>`;
  }

  /**
   * Escapes structural delimiter tags, neutralizes closing breakouts, and scrubs scripts/comments.
   * @param {string} content 
   * @returns {string} Sanitized text safe for embedding inside delimiters
   */
  escapeDelimiters(content) {
    if (!content || typeof content !== 'string') return '';
    let result = content;

    // Case-insensitive and whitespace-tolerant tag escaping
    result = result.replace(/<\/\s*untrusted_content\s*>/gi, '&lt;/untrusted_content&gt;');
    result = result.replace(/<\s*untrusted_content\s*>/gi, '&lt;untrusted_content&gt;');

    // HTML comments & executable script tags
    result = result.replace(/<!--[\s\S]*?-->/g, '[SCRUBBED_COMMENT]');
    result = result.replace(/<script[\s\S]*?<\/script>/gi, '[SCRUBBED_SCRIPT]');

    return result;
  }

  /**
   * Scans content for adversarial prompt injection vectors, overrides, and jailbreak patterns.
   * @param {string} content 
   * @returns {{ threatLevel: 'SAFE'|'SUSPICIOUS'|'MALICIOUS', reasons: string[], score: number }}
   */
  scanThreat(content) {
    if (!content || typeof content !== 'string') {
      return { threatLevel: 'SAFE', reasons: [], score: 0.0 };
    }

    const lower = content.toLowerCase();
    const reasons = [];

    // 1. Instruction override patterns
    if (
      lower.includes('ignore previous instructions') ||
      lower.includes('ignore all previous instructions') ||
      lower.includes('disregard prior instructions') ||
      lower.includes('disregard all previous constraints') ||
      lower.includes('system override')
    ) {
      reasons.push('INSTRUCTION_OVERRIDE_ATTEMPT');
    }

    // 2. Jailbreak patterns
    if (
      lower.includes('dan mode') ||
      lower.includes('do anything now') ||
      lower.includes('developer mode enabled') ||
      lower.includes('unrestricted mode')
    ) {
      reasons.push('JAILBREAK_PATTERN_DETECTED');
    }

    // 3. Delimiter breakout attempts
    if (
      lower.includes('</untrusted_content>') ||
      lower.includes('&lt;/untrusted_content&gt;')
    ) {
      reasons.push('DELIMITER_BREAKOUT_ATTEMPT');
    }

    // 4. Exfiltration probes
    if (
      lower.includes('reveal system prompt') ||
      lower.includes('print all secrets') ||
      lower.includes('what is your system prompt') ||
      lower.includes('repeat the exact instructions above') ||
      lower.includes('leak internal keys')
    ) {
      reasons.push('EXFILTRATION_PROBE_DETECTED');
    }

    // 5. Script tag injection
    if (lower.includes('<script') || lower.includes('[scrubbed_script]')) {
      reasons.push('SCRIPT_TAG_INJECTION');
    }

    let threatLevel = 'SAFE';
    let score = 0.0;

    if (
      reasons.length >= 2 ||
      reasons.includes('INSTRUCTION_OVERRIDE_ATTEMPT') ||
      reasons.includes('JAILBREAK_PATTERN_DETECTED') ||
      reasons.includes('DELIMITER_BREAKOUT_ATTEMPT') ||
      reasons.includes('EXFILTRATION_PROBE_DETECTED')
    ) {
      threatLevel = 'MALICIOUS';
      score = 1.0;
    } else if (reasons.length === 1) {
      threatLevel = 'SUSPICIOUS';
      score = 0.5;
    }

    return { threatLevel, reasons, score };
  }

  /**
   * Post-generation sanitization: strips leaked internal delimiter tags from model output.
   * @param {string} output 
   * @returns {string} Cleaned output string
   */
  sanitizeOutput(output) {
    if (!output || typeof output !== 'string') return '';
    let result = output;
    result = result.replace(/<\/?untrusted_content>/gi, '');
    result = result.replace(/&lt;\/?untrusted_content&gt;/gi, '');
    return result.trim();
  }
}

module.exports = { AikidoDefenseService };
