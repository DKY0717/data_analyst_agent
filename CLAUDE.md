# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data Analyst Agent — a natural language driven database analysis and SQL optimization system. Users ask data analysis questions in Chinese/English, and the system generates safe SQL, executes it, auto-repairs errors, and returns results with natural language explanations and charts.

**LLM Provider:** Qwen API (DashScope)
**Primary Database:** DuckDB (local), with PostgreSQL as optional alternative

## Commands

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
```

### Generate Database & Seed Data
```bash
cd backend
python -m database.seed_data
```

### Run Backend Server
```bash
cd backend
uvicorn app.main:app --reload
```
API docs at http://localhost:8000/docs

### Run Tests
```bash
cd backend
pytest                                    # all tests
pytest tests/test_sql_guard.py -v         # single test file
pytest tests/test_sql_guard.py::test_name -v  # single test
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:3000
npm run build    # production build
```

### Docker (Full Stack)
```bash
cp .env.example .env   # configure QWEN_API_KEY
docker-compose up -d
```

## Architecture

### Core Pipeline (LangGraph Agent Workflow)

```
Natural Language Question
  → Schema Loader (reads DB metadata via information_schema)
  → SQL Generator (Qwen API → structured JSON output)
  → SQL Guard (SQLGlot AST validation: SELECT/WITH only, auto LIMIT injection)
  → SQL Executor (DuckDB/PostgreSQL via SQLAlchemy)
  → SQL Repair Agent (if failure, max 3 retries using Qwen API)
  → Answer Generator (Qwen API → natural language explanation)
  → Optional: SQL Optimizer (EXPLAIN ANALYZE)
```

### Key Backend Modules

| Module | Path | Responsibility |
|---|---|---|
| Config | `backend/app/config.py` | Centralized env-based settings (`Settings` class) |
| SQL Guard | `backend/app/security/sql_guard.py` | SQLGlot-based AST safety validation |
| Schema Loader | `backend/app/db/schema_loader.py` | Reads DB schema via `information_schema` |
| Query Runner | `backend/app/db/query_runner.py` | Executes SQL with timeout and error capture |
| LLM Service | `backend/app/services/llm_service.py` | Qwen API client with retry logic |
| Agent Graph | `backend/app/agents/graph.py` | LangGraph `StateGraph` orchestrating the full pipeline |
| Agent State | `backend/app/agents/state.py` | `TypedDict` shared across all agent nodes |

### API Endpoints

- `POST /api/chat/query` — Main entry: natural language question → full pipeline result
- `GET /api/schema` — Returns database schema
- `GET /health` — Health check

### Frontend Stack

Vue 3 + Vite + Element Plus + Pinia (state) + ECharts (charts). Proxies `/api` to backend at `localhost:8000`.

### Database Schema (E-commerce Domain)

8 tables: `regions`, `customers`, `categories`, `products`, `orders`, `order_items`, `payments`, `refunds`. See `docs/database_design_md.md` for full design.

## Environment Variables

Copy `.env.example` to `.env`. Required:
- `QWEN_API_KEY` — DashScope API key
- `QWEN_MODEL` — defaults to `qwen-turbo`

## Key Design Constraints

- SQL Guard only allows `SELECT` and `WITH` statements; all DDL/DML is blocked
- Auto-injects `LIMIT 1000` if missing
- SQL Repair retries up to 3 times before giving up
- All LLM calls use structured JSON output (parsed from response)
- DuckDB dialect for SQL generation (not PostgreSQL)

## Documentation

- Development spec (Chinese): `docs/data_analyst_agent_开发文档_v_0_2.md`
- Database design: `docs/database_design_md.md`
- Implementation plan: `docs/superpowers/plans/2024-12-23-data-analyst-agent-implementation.md`

## Project Skills

Project-specific skills live in `skills/`. Read the relevant SKILL.md before working on the corresponding area:

| Skill | When to Read |
|-------|-------------|
| `sql-safety-rules` | Writing/modifying SQL Guard, SQL generation prompts, or SQL execution code |
| `qwen-api-patterns` | Writing/modifying code that calls Qwen API (LLM service, agents) |
| `agent-workflow-constraints` | Writing/modifying LangGraph agent code, workflow graph, or agent state |
| `ecommerce-schema` | Writing SQL queries, schema loader code, seed data, or test fixtures |
| `comment-key-steps` | Writing any new code file — add Chinese comments at key steps for learning |
| `verify-after-write` | After writing any new code — run minimal verification before committing |
| `work-diary` | Starting/ending a session — read and update `logs/work-diary.md` for continuity |
| `ecc-guide` | Guide users through ECC's current agents, skills, commands, hooks, rules, install profiles, and project onboarding |
