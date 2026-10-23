# BigQuery SQL Optimization Skill Dump
Source: C:\Users\Lesia Eden\.gemini\config\skills\bigquery-sql\SKILL.md

Refer to upstream skill. Core rules:
- Column Pruning, Predicate pushdown, Early aggregation.
- Partitioning and clustering: Partition base tables by DATE(extracted_at) and cluster by inferred_domain, app_name.
