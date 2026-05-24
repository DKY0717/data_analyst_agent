---
name: qwen-api-patterns
description: Use when writing code that calls Qwen API (DashScope) for SQL generation, SQL repair, or answer generation in this project
---

# Qwen API Patterns

## Overview

All LLM calls in this project go through `backend/app/services/llm_service.py` using Qwen API (DashScope). Every call must produce structured JSON output.

## API Endpoint

```
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
```

## Request Format

```python
payload = {
    "model": "qwen-turbo",  # from settings.QWEN_MODEL
    "input": {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."}
        ]
    },
    "parameters": {
        "result_format": "message",
        "temperature": 0.1,
        "max_tokens": 2000
    }
}
```

## Auth Header

```
Authorization: Bearer {QWEN_API_KEY}
```

## Response Parsing

```python
content = result["output"]["choices"][0]["message"]["content"]
data = json.loads(content)  # Always expect JSON
```

## Three Call Patterns

| Agent | Purpose | Output |
|-------|---------|--------|
| SQL Generator | Generate SQL from question + schema | `{"sql": "...", "tables": [...], "explanation": "..."}` |
| SQL Repair | Fix failed SQL with error context | `{"repaired_sql": "...", "repair_reason": "..."}` |
| Answer Generator | Explain query results | Natural language text (not JSON) |

## Retry Logic

- Max 3 retries with exponential backoff (2^attempt seconds)
- Timeout: 30 seconds per call
- Custom exceptions: `LLMError`, `LLMTimeoutError`, `LLMResponseError`

## Temperature Settings

- SQL generation: 0.1 (deterministic)
- SQL repair: 0.1 (deterministic)
- Answer generation: 0.3 (slightly creative)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using raw text output | Always request structured JSON from Qwen |
| Hardcoding API key | Use `settings.QWEN_API_KEY` from config |
| No timeout | Always set `timeout=30` in httpx |
| Catching all exceptions | Catch specific httpx exceptions for proper retry |
