---
name: sql-safety-rules
description: Use when writing or modifying SQL Guard code, SQL generation prompts, or any code that handles SQL execution in this project
---

# SQL Safety Rules

## Overview

All SQL in this project MUST pass through SQL Guard (SQLGlot AST validation) before execution. Never execute raw LLM-generated SQL directly.

## Allowed Statements

- `SELECT`
- `WITH` (CTE)
- `EXPLAIN`

## Blocked Statements

DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, MERGE, CALL, EXECUTE, GRANT, REVOKE

## Additional Constraints

- No multi-statement execution (one SQL per call)
- No system table access
- No file write operations
- No external function calls
- Auto-inject `LIMIT 1000` if SELECT has no LIMIT
- SQL dialect is **DuckDB** (not PostgreSQL)

## Implementation Location

- Guard: `backend/app/security/sql_guard.py`
- Uses SQLGlot for AST parsing
- Tests: `backend/tests/test_sql_guard.py`

## When Writing SQL Generation Prompts

Prompts to Qwen must instruct it to output DuckDB-dialect SQL. Include in system prompt:
- "只输出 SELECT 或 WITH 语句"
- "使用 DuckDB 方言"
- "不要使用不存在的字段"

## Red Flags

| Thought | Reality |
|---------|---------|
| "It's just a test query" | Test queries also need guard validation |
| "I'll skip the guard for debugging" | Use EXPLAIN instead of skipping guard |
| "PostgreSQL syntax works too" | This project uses DuckDB dialect. Stick to it. |
