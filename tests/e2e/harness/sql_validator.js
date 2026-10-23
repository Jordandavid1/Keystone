'use strict';

/**
 * BigQuery SQL Syntax & Resource Attribution Validator
 * Validates BigQuery AI/ML grammar rules and CLI attribution flags per PROJECT.md.
 */

const MUTATING_BQ_SUBCOMMANDS = ['query', 'load', 'extract', 'mk', 'update', 'cp'];
const READONLY_BQ_SUBCOMMANDS = ['show', 'ls', 'version', 'rm', 'cancel', 'head'];

function validateBigQuerySql(sql) {
  const errors = [];
  const normalized = sql.replace(/\s+/g, ' ').trim();

  // Check TVF placement: AI.GENERATE_EMBEDDING must be in FROM clause
  if (/SELECT\s+[^;]*AI\.GENERATE_EMBEDDING/i.test(normalized)) {
    // If it's in SELECT clause and not part of a FROM subquery
    const selectPart = normalized.split(/FROM/i)[0];
    if (/AI\.GENERATE_EMBEDDING/i.test(selectPart)) {
      errors.push('TVF_IN_SELECT: AI.GENERATE_EMBEDDING is a Table-Valued Function and MUST appear in the FROM clause, not SELECT.');
    }
  }

  // Check TVF placement: VECTOR_SEARCH must be in FROM clause
  if (/SELECT\s+[^;]*VECTOR_SEARCH\s*\(/i.test(normalized)) {
    const selectPart = normalized.split(/FROM/i)[0];
    if (/VECTOR_SEARCH\s*\(/i.test(selectPart)) {
      errors.push('TVF_IN_SELECT: VECTOR_SEARCH is a Table-Valued Function and MUST appear in the FROM clause, not SELECT.');
    }
  }

  // Check output_schema in AI.GENERATE: must be quoted string
  const outputSchemaMatch = normalized.match(/output_schema\s*=>\s*(['"][^'"]*['"]|[^,\)]+)/i);
  if (outputSchemaMatch) {
    const val = outputSchemaMatch[1].trim();
    if (!(/^['"].*['"]$/.test(val))) {
      errors.push('UNQUOTED_OUTPUT_SCHEMA: output_schema parameter in AI.GENERATE must be a quoted string literal.');
    }
  }

  // Check vector search top_k: must be positive integer
  const topKMatch = normalized.match(/top_k\s*=>\s*(\d+)/i);
  if (topKMatch) {
    const k = parseInt(topKMatch[1], 10);
    if (k <= 0) {
      errors.push('INVALID_TOP_K: top_k in VECTOR_SEARCH must be greater than 0.');
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function validateBqCliAttribution(command) {
  const errors = [];
  const tokens = command.trim().split(/\s+/);

  if (tokens[0] !== 'bq') {
    errors.push('NOT_BQ_COMMAND: Command must begin with "bq".');
    return { valid: false, errors };
  }

  const subcommand = tokens[1];
  const hasLabel = command.includes('--label') || command.includes('--labels');
  const hasCorrectLabel = /--label\s+datacloud:antigravity/.test(command) || /--label=datacloud:antigravity/.test(command);

  if (MUTATING_BQ_SUBCOMMANDS.includes(subcommand)) {
    if (!hasLabel) {
      errors.push(`MISSING_LABEL: Mutating subcommand 'bq ${subcommand}' MUST include '--label datacloud:antigravity'.`);
    } else if (!hasCorrectLabel) {
      errors.push(`INVALID_LABEL_SYNTAX: Mutating subcommand 'bq ${subcommand}' has invalid label format; must be exactly 'datacloud:antigravity'.`);
    }
  } else if (READONLY_BQ_SUBCOMMANDS.includes(subcommand)) {
    if (hasLabel) {
      errors.push(`ILLEGAL_LABEL_FLAG: Read-only subcommand 'bq ${subcommand}' rejects '--label'; label is prohibited.`);
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function validateGcloudAttribution(command) {
  const errors = [];
  if (!command.includes('CLOUDSDK_METRICS_ENVIRONMENT')) {
    errors.push('MISSING_METRICS_ENV: gcloud command must include CLOUDSDK_METRICS_ENVIRONMENT.');
  } else if (!command.includes('datacloud.antigravity')) {
    errors.push('INVALID_METRICS_ENV: CLOUDSDK_METRICS_ENVIRONMENT must contain "datacloud.antigravity".');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

module.exports = {
  validateBigQuerySql,
  validateBqCliAttribution,
  validateGcloudAttribution
};
