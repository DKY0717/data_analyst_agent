---
name: agent-workflow-constraints
description: Use when writing or modifying LangGraph agent code, workflow graph, or agent state in this project
---

# Agent Workflow Constraints

## Overview

The agent pipeline is a LangGraph `StateGraph` with specific node ordering and state management rules.

## Pipeline Order

```
Schema Loader → SQL Generator → SQL Guard → SQL Executor
                                              ↓ (on failure)
                                          SQL Repair → SQL Guard → SQL Executor
                                              ↓ (max 3 retries)
                                          Answer Generator
```

## State Definition

All nodes share `AgentState` (TypedDict) defined in `backend/app/agents/state.py`:

```python
class AgentState(TypedDict):
    question: str
    schema_context: dict
    generated_sql: str
    validated_sql: str
    is_sql_safe: bool
    validation_error: str | None
    execution_success: bool
    query_result: dict | None
    execution_error: str | None
    retry_count: int
    answer: str | None
    optimization_suggestions: list[str]
```

## Hard Limits

- **Max repair retries: 3** — after 3 failures, return error to user
- **SQL must pass Guard before execution** — no bypassing validation
- **Each node reads from and writes to shared state** — no side channels

## Conditional Edges

```python
# After SQL Guard:
if is_sql_safe → SQL Executor
else → return validation_error

# After SQL Executor:
if execution_success → Answer Generator
elif retry_count < 3 → SQL Repair
else → return execution_error
```

## Node Files

| Node | File |
|------|------|
| Graph definition | `backend/app/agents/graph.py` |
| State | `backend/app/agents/state.py` |
| SQL Generator | `backend/app/agents/sql_generator.py` |
| SQL Repair | `backend/app/agents/sql_repair.py` |
| Answer Generator | `backend/app/agents/answer_generator.py` |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping Guard after Repair | Repair output MUST go through Guard again |
| No retry limit on Repair | Always check `retry_count < 3` |
| Modifying state outside nodes | All state changes happen inside nodes |
| Using PostgreSQL dialect | Use DuckDB dialect for SQL generation |
