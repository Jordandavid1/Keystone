# BigQuery AI & ML Skill Dump
Source: C:\Users\Lesia Eden\.gemini\config\skills\bigquery-ai-ml\SKILL.md

Refer to upstream skill. Core rules:
- Connection ID: 'DEFAULT' for remote models
- TVFs (AI.GENERATE_EMBEDDING, VECTOR_SEARCH, AI.GENERATE_TABLE, etc.) MUST be placed in the FROM clause, NEVER in SELECT.
- Schema Quotes: Ensure output_schema string is enclosed in quotes.
- Procedures: AI.GENERATE, AI.SIMILARITY, AI.CLASSIFY.
