# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Data Analyst Agent — a natural language driven database analysis and SQL optimization system. Users ask data analysis questions in Chinese/English, and the system generates safe SQL, executes it, auto-repairs errors, and returns results with natural language explanations and charts.

**LLM Provider:** OpenAI-compatible LLM API. Current defaults use MiMo v2.5 Pro; `QWEN_*` environment variable names are retained for backward compatibility and can also point to Qwen/DashScope-compatible endpoints.
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
  → Intent Guard (deterministic safety rules, blocks before any LLM/DB call)
  → Parse Intent (rule_parser + llm_parser → merger, extracts metrics/dimensions/filters/ranking)
  → Ground Schema (maps business concepts to physical Schema expressions + JOIN routes)
  → Assess Clarification (low confidence / missing slots → structured clarification request)
  → Schema Loader (reads DB metadata via information_schema)
  → SQL Generator (OpenAI-compatible LLM API → structured JSON output, injected with intent signals)
  → SQL Guard (SQLGlot AST validation: SELECT/WITH only, auto LIMIT injection)
  → SQL Executor (DuckDB/PostgreSQL via SQLAlchemy)
  → SQL Repair Agent (if failure, max 3 retries using the configured LLM API)
  → SQL Optimizer (AST/result checks → optional EXPLAIN ANALYZE)
  → Answer Generator (configured LLM API → natural language explanation)
```

### Key Backend Modules

| Module | Path | Responsibility |
|---|---|---|
| Config | `backend/app/config.py` | Centralized env-based settings (`Settings` class) |
| Intent Guard | `backend/app/security/intent_guard.py` | Deterministic safety rules, blocks before LLM/DB access |
| SQL Guard | `backend/app/security/sql_guard.py` | SQLGlot-based AST safety validation |
| Schema Loader | `backend/app/db/schema_loader.py` | Reads DB schema via `information_schema` |
| Query Runner | `backend/app/db/query_runner.py` | Executes SQL with timeout and error capture |
| LLM Service | `backend/app/services/llm_service.py` | OpenAI-compatible LLM client with retry logic |
| Agent Graph | `backend/app/agents/graph.py` | LangGraph `StateGraph` orchestrating the full pipeline |
| Agent State | `backend/app/agents/state.py` | `TypedDict` shared across all agent nodes |
| Analysis Intent | `backend/app/analysis_intent/` | Rule parser + LLM parser + merger for intent extraction |
| Grounding | `backend/app/agents/grounding.py` | Maps business concepts to physical Schema expressions |
| Clarification | `backend/app/agents/clarification.py` | Low-confidence/missing-slot clarification engine |

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
- `QWEN_API_KEY` — API key for the configured OpenAI-compatible endpoint
- `QWEN_API_URL` — defaults to the MiMo OpenAI-compatible chat completions endpoint
- `QWEN_MODEL` — defaults to `mimo-v2.5-pro`

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
| `qwen-api-patterns` | Writing/modifying code that calls the OpenAI-compatible LLM API (LLM service, agents) |
| `agent-workflow-constraints` | Writing/modifying LangGraph agent code, workflow graph, or agent state |
| `ecommerce-schema` | Writing SQL queries, schema loader code, seed data, or test fixtures |
| `comment-key-steps` | Writing any new code file — add Chinese comments at key steps for learning |
| `verify-after-write` | After writing any new code — run minimal verification before committing |
| `work-diary` | Starting/ending a session — read and update `logs/work-diary.md` for continuity |
| `ecc-guide` | Guide users through ECC's current agents, skills, commands, hooks, rules, install profiles, and project onboarding |
