# Data Analyst Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete Data Analyst Agent system that converts natural language questions to safe SQL queries, executes them, and provides intelligent explanations with optimization suggestions.

**Architecture:** Multi-agent workflow using LangGraph for orchestration, FastAPI for backend API, Vue 3 + Vite for frontend, DuckDB for database, and Qwen API for LLM capabilities. The system follows a pipeline: Schema Loading → SQL Generation → SQL Safety Validation → SQL Execution → Error Repair → Answer Generation.

**Tech Stack:** Python 3.10+, FastAPI, LangGraph, SQLGlot, DuckDB, SQLAlchemy, Vue 3, Vite, Element Plus, ECharts, Qwen API

---

## File Structure

Before defining tasks, here's the complete file structure that will be created:

### Backend Files
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── query.py              # Query API endpoints
│   │   ├── schema.py             # Schema API endpoints
│   │   └── health.py             # Health check endpoint
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── graph.py              # LangGraph workflow definition
│   │   ├── state.py              # Agent state definition
│   │   ├── sql_generator.py      # SQL generation agent
│   │   ├── sql_repair.py         # SQL repair agent
│   │   └── answer_generator.py   # Answer generation agent
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py         # Database connection management
│   │   ├── schema_loader.py      # Schema loading utility
│   │   └── query_runner.py       # SQL execution utility
│   ├── security/
│   │   ├── __init__.py
│   │   └── sql_guard.py          # SQL safety validation
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm_service.py        # LLM API service
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic models
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # Logging configuration
│       └── exceptions.py         # Custom exceptions
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Test fixtures
│   ├── test_sql_guard.py         # SQL Guard tests
│   ├── test_schema_loader.py     # Schema Loader tests
│   ├── test_query_runner.py      # Query Runner tests
│   └── test_agent_graph.py       # Agent workflow tests
├── requirements.txt              # Python dependencies
└── Dockerfile                    # Backend Docker image
```

### Frontend Files
```
frontend/
├── src/
│   ├── api/
│   │   └── agent.js              # API client
│   ├── components/
│   │   ├── QueryInput.vue        # Query input component
│   │   ├── SQLPanel.vue          # SQL display component
│   │   ├── ResultTable.vue       # Result table component
│   │   ├── ChartPanel.vue        # Chart display component
│   │   └── AnswerPanel.vue       # Answer display component
│   ├── views/
│   │   └── Home.vue              # Main page
│   ├── stores/
│   │   └── query.js              # Pinia store
│   ├── App.vue                   # Root component
│   └── main.js                   # Application entry
├── package.json                  # Node.js dependencies
├── vite.config.js                # Vite configuration
└── index.html                    # HTML template
```

### Database Files
```
database/
├── init.sql                      # Database schema
└── seed_data.py                  # Data generation script
```

### Documentation Files
```
docs/
├── data_analyst_agent_开发文档_v_0_2.md
├── database_design_md.md
├── api_design.md
└── agent_workflow.md
```

---

## Task 1: Project Setup and Directory Structure

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/utils/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `frontend/` (empty directory)
- Create: `database/` (empty directory)

- [ ] **Step 1: Create backend directory structure**

```bash
mkdir -p backend/app/api
mkdir -p backend/app/agents
mkdir -p backend/app/db
mkdir -p backend/app/security
mkdir -p backend/app/services
mkdir -p backend/app/models
mkdir -p backend/app/utils
mkdir -p backend/tests
```

- [ ] **Step 2: Create __init__.py files**

```bash
touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/agents/__init__.py
touch backend/app/db/__init__.py
touch backend/app/security/__init__.py
touch backend/app/services/__init__.py
touch backend/app/models/__init__.py
touch backend/app/utils/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 3: Create frontend and database directories**

```bash
mkdir -p frontend
mkdir -p database
```

- [ ] **Step 4: Create requirements.txt**

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.2
sqlalchemy==2.0.23
sqlglot==20.0.0
duckdb==0.9.2
httpx==0.25.2
python-dotenv==1.0.0
pytest==7.4.3
pytest-asyncio==0.23.2
```

- [ ] **Step 5: Create .env.example**

```env
# Qwen API Configuration
QWEN_API_KEY=your_api_key_here
QWEN_API_URL=https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
QWEN_MODEL=qwen-turbo

# Database Configuration
DATABASE_URL=duckdb:///./data/database.duckdb

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true
LOG_LEVEL=INFO
```

- [ ] **Step 6: Commit**

```bash
git add backend/ frontend/ database/ requirements.txt .env.example
git commit -m "feat: initialize project directory structure"
```

---

## Task 2: Configuration Management

**Files:**
- Create: `backend/app/config.py`

- [ ] **Step 1: Write configuration module**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings"""

    # API Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "duckdb:///./data/database.duckdb")

    # Qwen API Configuration
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_URL: str = os.getenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-turbo")

    # SQL Configuration
    SQL_TIMEOUT: int = int(os.getenv("SQL_TIMEOUT", "30"))
    SQL_MAX_ROWS: int = int(os.getenv("SQL_MAX_ROWS", "1000"))
    SQL_MAX_RETRIES: int = int(os.getenv("SQL_MAX_RETRIES", "3"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOG_DIR: Path = BASE_DIR / "logs"

settings = Settings()

# Create directories if they don't exist
settings.DATA_DIR.mkdir(exist_ok=True)
settings.LOG_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add configuration management"
```

---

## Task 3: Logging Configuration

**Files:**
- Create: `backend/app/utils/logger.py`

- [ ] **Step 1: Write logging configuration**

```python
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

def setup_logging() -> logging.Logger:
    """Configure application logging"""

    # Create logger
    logger = logging.getLogger("data_analyst_agent")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler
    log_file = settings.LOG_DIR / "app.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# Initialize logger
logger = setup_logging()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/utils/logger.py
git commit -m "feat: add logging configuration"
```

---

## Task 4: Custom Exceptions

**Files:**
- Create: `backend/app/utils/exceptions.py`

- [ ] **Step 1: Write custom exceptions**

```python
class AppException(Exception):
    """Base application exception"""
    pass

class DatabaseError(AppException):
    """Database operation error"""
    pass

class SQLGuardError(AppException):
    """SQL safety validation error"""
    pass

class SQLExecutionError(AppException):
    """SQL execution error"""
    pass

class SQLRepairError(AppException):
    """SQL repair error"""
    pass

class LLMError(AppException):
    """LLM API error"""
    pass

class LLMTimeoutError(LLMError):
    """LLM API timeout"""
    pass

class LLMResponseError(LLMError):
    """LLM API response error"""
    pass

class SchemaLoadError(AppException):
    """Schema loading error"""
    pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/utils/exceptions.py
git commit -m "feat: add custom exceptions"
```

---

## Task 5: Pydantic Models

**Files:**
- Create: `backend/app/models/schemas.py`

- [ ] **Step 1: Write Pydantic models**

```python
from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict
from datetime import datetime

# Request Models
class QueryRequest(BaseModel):
    """Query request model"""
    question: str = Field(..., min_length=1, max_length=1000, description="Natural language question")

class SQLValidateRequest(BaseModel):
    """SQL validation request model"""
    sql: str = Field(..., min_length=1, description="SQL to validate")

class SQLExecuteRequest(BaseModel):
    """SQL execution request model"""
    sql: str = Field(..., min_length=1, description="SQL to execute")

# Response Models
class SuccessResponse(BaseModel):
    """Success response model"""
    code: int = 200
    message: str = "success"
    data: Any

class ErrorResponse(BaseModel):
    """Error response model"""
    error_code: int
    error_type: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None

class QueryResponse(BaseModel):
    """Query response model"""
    question: str
    sql: str
    is_sql_safe: bool
    columns: List[str]
    rows: List[List[Any]]
    answer: str
    execution_time_ms: int
    retry_count: int
    optimization_suggestions: List[str] = []

class SchemaResponse(BaseModel):
    """Schema response model"""
    tables: Dict[str, List[Dict[str, str]]]

class SQLValidateResponse(BaseModel):
    """SQL validation response model"""
    is_safe: bool
    sanitized_sql: str
    reason: Optional[str] = None

class SQLExecuteResponse(BaseModel):
    """SQL execution response model"""
    success: bool
    columns: List[str] = []
    rows: List[List[Any]] = []
    execution_time_ms: int = 0
    error: Optional[str] = None
    error_type: Optional[str] = None

class SQLGeneratorOutput(BaseModel):
    """SQL generator output model"""
    sql: str
    tables: List[str]
    columns: List[str]
    explanation: str

class SQLRepairOutput(BaseModel):
    """SQL repair output model"""
    repaired_sql: str
    repair_reason: str

class AgentState(BaseModel):
    """Agent state model"""
    question: str
    schema_context: Optional[Dict[str, Any]] = None
    generated_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    is_sql_safe: bool = False
    validation_error: Optional[str] = None
    execution_success: bool = False
    query_result: Optional[Dict[str, Any]] = None
    execution_error: Optional[str] = None
    retry_count: int = 0
    answer: Optional[str] = None
    optimization_suggestions: List[str] = []
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/schemas.py
git commit -m "feat: add Pydantic models"
```

---

## Task 6: Database Connection Management

**Files:**
- Create: `backend/app/db/connection.py`

- [ ] **Step 1: Write database connection module**

```python
import duckdb
from contextlib import contextmanager
from pathlib import Path

from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import DatabaseError

class DatabaseConnection:
    """Database connection manager"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(settings.DATA_DIR / "database.duckdb")
        self._connection = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get database connection"""
        if self._connection is None:
            try:
                self._connection = duckdb.connect(self.db_path)
                logger.info(f"Connected to database: {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise DatabaseError(f"Failed to connect to database: {e}")
        return self._connection

    def close(self):
        """Close database connection"""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

    @contextmanager
    def get_session(self):
        """Get database session with context manager"""
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error(f"Database session error: {e}")
            raise DatabaseError(f"Database session error: {e}")

# Global database connection instance
db_connection = DatabaseConnection()

def get_db():
    """Dependency for FastAPI"""
    return db_connection.get_session()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/db/connection.py
git commit -m "feat: add database connection management"
```

---

## Task 7: Schema Loader

**Files:**
- Create: `backend/app/db/schema_loader.py`
- Create: `backend/tests/test_schema_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_schema_loader.py
import pytest
from app.db.schema_loader import SchemaLoader

def test_schema_loader_get_tables():
    """Test getting list of tables"""
    loader = SchemaLoader()
    tables = loader.get_tables()
    assert isinstance(tables, list)
    assert len(tables) > 0

def test_schema_loader_get_table_schema():
    """Test getting table schema"""
    loader = SchemaLoader()
    tables = loader.get_tables()
    if tables:
        table_name = tables[0]
        schema = loader.get_table_schema(table_name)
        assert "columns" in schema
        assert isinstance(schema["columns"], list)

def test_schema_loader_get_full_schema():
    """Test getting full database schema"""
    loader = SchemaLoader()
    schema = loader.get_full_schema()
    assert "tables" in schema
    assert isinstance(schema["tables"], dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_schema_loader.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.db.schema_loader'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db/schema_loader.py
from typing import Dict, List, Any

from app.db.connection import db_connection
from app.utils.logger import logger
from app.utils.exceptions import SchemaLoadError

class SchemaLoader:
    """Database schema loader"""

    def __init__(self):
        self.db = db_connection

    def get_tables(self) -> List[str]:
        """Get list of all tables in database"""
        try:
            with self.db.get_session() as conn:
                result = conn.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main'
                    ORDER BY table_name
                """).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            raise SchemaLoadError(f"Failed to get tables: {e}")

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema for a specific table"""
        try:
            with self.db.get_session() as conn:
                # Get column information
                columns = conn.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """).fetchall()

                # Get primary key information
                primary_keys = conn.execute(f"""
                    SELECT column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_name = '{table_name}'
                    AND tc.constraint_type = 'PRIMARY KEY'
                """).fetchall()

                return {
                    "table_name": table_name,
                    "columns": [
                        {
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES"
                        }
                        for col in columns
                    ],
                    "primary_keys": [pk[0] for pk in primary_keys]
                }
        except Exception as e:
            logger.error(f"Failed to get schema for table {table_name}: {e}")
            raise SchemaLoadError(f"Failed to get schema for table {table_name}: {e}")

    def get_full_schema(self) -> Dict[str, Any]:
        """Get full database schema"""
        try:
            tables = self.get_tables()
            schema = {}

            for table in tables:
                schema[table] = self.get_table_schema(table)

            return {"tables": schema}
        except Exception as e:
            logger.error(f"Failed to get full schema: {e}")
            raise SchemaLoadError(f"Failed to get full schema: {e}")

# Global schema loader instance
schema_loader = SchemaLoader()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_schema_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/schema_loader.py backend/tests/test_schema_loader.py
git commit -m "feat: add schema loader"
```

---

## Task 8: SQL Guard (Safety Validation)

**Files:**
- Create: `backend/app/security/sql_guard.py`
- Create: `backend/tests/test_sql_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sql_guard.py
import pytest
from app.security.sql_guard import SQLGuard

def test_sql_guard_select_safe():
    """Test SELECT statement is safe"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders")
    assert result["is_safe"] == True

def test_sql_guard_drop_unsafe():
    """Test DROP statement is unsafe"""
    guard = SQLGuard()
    result = guard.validate("DROP TABLE orders")
    assert result["is_safe"] == False

def test_sql_guard_delete_unsafe():
    """Test DELETE statement is unsafe"""
    guard = SQLGuard()
    result = guard.validate("DELETE FROM orders")
    assert result["is_safe"] == False

def test_sql_guard_update_unsafe():
    """Test UPDATE statement is unsafe"""
    guard = SQLGuard()
    result = guard.validate("UPDATE orders SET status='x'")
    assert result["is_safe"] == False

def test_sql_guard_insert_unsafe():
    """Test INSERT statement is unsafe"""
    guard = SQLGuard()
    result = guard.validate("INSERT INTO orders VALUES (1, 2)")
    assert result["is_safe"] == False

def test_sql_guard_multi_statement_unsafe():
    """Test multi-statement is unsafe"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders; DROP TABLE orders")
    assert result["is_safe"] == False

def test_sql_guard_with_cte_safe():
    """Test WITH CTE is safe"""
    guard = SQLGuard()
    result = guard.validate("WITH t AS (SELECT * FROM orders) SELECT * FROM t")
    assert result["is_safe"] == True

def test_sql_guard_add_limit():
    """Test automatic LIMIT addition"""
    guard = SQLGuard()
    result = guard.validate("SELECT * FROM orders")
    assert "LIMIT" in result["sanitized_sql"].upper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sql_guard.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.security.sql_guard'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/security/sql_guard.py
import sqlglot
from typing import Dict, Any, Optional

from app.utils.logger import logger
from app.utils.exceptions import SQLGuardError
from app.config import settings

class SQLGuard:
    """SQL safety validation using SQLGlot"""

    # Allowed statement types
    ALLOWED_STATEMENTS = {"SELECT", "WITH"}

    # Blocked statement types
    BLOCKED_STATEMENTS = {
        "DROP", "DELETE", "UPDATE", "INSERT",
        "ALTER", "TRUNCATE", "CREATE", "MERGE",
        "CALL", "EXECUTE", "GRANT", "REVOKE"
    }

    def __init__(self, max_rows: int = None):
        self.max_rows = max_rows or settings.SQL_MAX_ROWS

    def validate(self, sql: str) -> Dict[str, Any]:
        """
        Validate SQL safety

        Returns:
            Dict with keys: is_safe, sanitized_sql, reason
        """
        try:
            # Parse SQL
            parsed = sqlglot.parse_one(sql, dialect="duckdb")

            # Check statement type
            statement_type = parsed.key.upper()

            if statement_type not in self.ALLOWED_STATEMENTS:
                if statement_type in self.BLOCKED_STATEMENTS:
                    return {
                        "is_safe": False,
                        "sanitized_sql": sql,
                        "reason": f"Blocked statement type: {statement_type}"
                    }
                else:
                    return {
                        "is_safe": False,
                        "sanitized_sql": sql,
                        "reason": f"Unknown statement type: {statement_type}"
                    }

            # Check for multiple statements
            statements = sqlglot.parse(sql, dialect="duckdb")
            if len(statements) > 1:
                return {
                    "is_safe": False,
                    "sanitized_sql": sql,
                    "reason": "Multiple statements not allowed"
                }

            # Sanitize SQL
            sanitized_sql = self._sanitize_sql(parsed)

            return {
                "is_safe": True,
                "sanitized_sql": sanitized_sql,
                "reason": None
            }

        except Exception as e:
            logger.error(f"SQL validation error: {e}")
            return {
                "is_safe": False,
                "sanitized_sql": sql,
                "reason": f"SQL parsing error: {str(e)}"
            }

    def _sanitize_sql(self, parsed) -> str:
        """Sanitize SQL by adding LIMIT if not present"""
        sql = parsed.sql(dialect="duckdb")

        # Add LIMIT if not present
        if "LIMIT" not in sql.upper():
            sql = f"{sql} LIMIT {self.max_rows}"

        return sql

# Global SQL guard instance
sql_guard = SQLGuard()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sql_guard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/sql_guard.py backend/tests/test_sql_guard.py
git commit -m "feat: add SQL safety validation"
```

---

## Task 9: Query Runner

**Files:**
- Create: `backend/app/db/query_runner.py`
- Create: `backend/tests/test_query_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_query_runner.py
import pytest
from app.db.query_runner import QueryRunner

def test_query_runner_execute_select():
    """Test executing SELECT query"""
    runner = QueryRunner()
    result = runner.execute("SELECT 1 as test")
    assert result["success"] == True
    assert "columns" in result
    assert "rows" in result

def test_query_runner_execution_time():
    """Test execution time tracking"""
    runner = QueryRunner()
    result = runner.execute("SELECT 1 as test")
    assert "execution_time_ms" in result
    assert isinstance(result["execution_time_ms"], (int, float))

def test_query_runner_error_handling():
    """Test error handling for invalid SQL"""
    runner = QueryRunner()
    result = runner.execute("SELECT * FROM non_existent_table")
    assert result["success"] == False
    assert "error" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_query_runner.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.db.query_runner'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db/query_runner.py
import time
from typing import Dict, Any, List

from app.db.connection import db_connection
from app.utils.logger import logger
from app.utils.exceptions import SQLExecutionError
from app.config import settings

class QueryRunner:
    """SQL query execution utility"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.SQL_TIMEOUT

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query

        Returns:
            Dict with keys: success, columns, rows, execution_time_ms, error, error_type
        """
        start_time = time.time()

        try:
            with db_connection.get_session() as conn:
                # Set query timeout
                conn.execute(f"SET statement_timeout = '{self.timeout}s'")

                # Execute query
                result = conn.execute(sql)

                # Get column names
                columns = [desc[0] for desc in result.description] if result.description else []

                # Fetch results
                rows = result.fetchall()

                # Convert rows to list of lists
                rows_list = [list(row) for row in rows]

                execution_time = int((time.time() - start_time) * 1000)

                logger.info(f"Query executed successfully in {execution_time}ms")

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows_list,
                    "execution_time_ms": execution_time,
                    "row_count": len(rows_list)
                }

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_type = type(e).__name__

            logger.error(f"Query execution failed: {e}")

            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time,
                "error": str(e),
                "error_type": error_type
            }

# Global query runner instance
query_runner = QueryRunner()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_query_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/query_runner.py backend/tests/test_query_runner.py
git commit -m "feat: add query runner"
```

---

## Task 10: LLM Service

**Files:**
- Create: `backend/app/services/llm_service.py`

- [ ] **Step 1: Write LLM service**

```python
import httpx
import json
import asyncio
from typing import Dict, Any, Optional

from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import LLMError, LLMTimeoutError, LLMResponseError

class LLMService:
    """LLM API service for Qwen"""

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.api_url = settings.QWEN_API_URL
        self.model = settings.QWEN_MODEL

    async def call_api(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Call Qwen API

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            API response as dictionary
        """
        if not self.api_key:
            raise LLMError("QWEN_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "result_format": "message",
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )
                response.raise_for_status()

                result = response.json()

                # Extract content from response
                content = result["output"]["choices"][0]["message"]["content"]

                # Try to parse as JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"content": content}

            except httpx.TimeoutException:
                logger.error("LLM API call timed out")
                raise LLMTimeoutError("LLM API call timed out")
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API HTTP error: {e.response.status_code}")
                raise LLMResponseError(f"LLM API HTTP error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"LLM API call failed: {e}")
                raise LLMError(f"LLM API call failed: {e}")

    async def call_with_retry(
        self,
        prompt: str,
        system_prompt: str = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Call LLM API with retry logic

        Args:
            prompt: User prompt
            system_prompt: System prompt
            max_retries: Maximum number of retries

        Returns:
            API response as dictionary
        """
        for attempt in range(max_retries):
            try:
                return await self.call_api(prompt, system_prompt)
            except (LLMTimeoutError, LLMResponseError) as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"LLM API call failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            except LLMError:
                raise

# Global LLM service instance
llm_service = LLMService()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/llm_service.py
git commit -m "feat: add LLM service"
```

---

## Task 11: SQL Generator Agent

**Files:**
- Create: `backend/app/agents/sql_generator.py`

- [ ] **Step 1: Write SQL generator agent**

```python
import json
from typing import Dict, Any

from app.services.llm_service import llm_service
from app.models.schemas import SQLGeneratorOutput
from app.utils.logger import logger
from app.utils.exceptions import LLMError

SQL_GENERATOR_PROMPT = """
你是一个专业的 SQL 生成助手。根据用户的问题和数据库 Schema，生成安全、正确的 SQL 查询。

## 数据库 Schema

{schema_context}

## 用户问题

{question}

## 要求

1. 只输出 JSON 格式，不要输出其他内容
2. 只生成 SELECT 或 WITH 查询，禁止生成 DROP、DELETE、UPDATE、INSERT 等危险语句
3. SQL 方言使用 DuckDB
4. 字段必须来自提供的 Schema，不要编造不存在的字段
5. 如果问题不明确，生成最可能的查询

## 输出格式

```json
{{
  "sql": "生成的 SQL 语句",
  "tables": ["使用的表名"],
  "columns": ["使用的字段名"],
  "explanation": "SQL 查询逻辑的简要说明"
}}
```

请严格按照上述格式输出 JSON。
"""

class SQLGenerator:
    """SQL generation agent"""

    async def generate(self, question: str, schema_context: Dict[str, Any]) -> SQLGeneratorOutput:
        """
        Generate SQL from natural language question

        Args:
            question: Natural language question
            schema_context: Database schema context

        Returns:
            SQLGeneratorOutput with generated SQL
        """
        try:
            # Format schema context
            schema_str = self._format_schema(schema_context)

            # Create prompt
            prompt = SQL_GENERATOR_PROMPT.format(
                schema_context=schema_str,
                question=question
            )

            # Call LLM
            system_prompt = "你是一个 SQL 生成助手，根据用户问题和数据库 Schema 生成 SQL。只输出 JSON 格式。"
            result = await llm_service.call_with_retry(prompt, system_prompt)

            # Parse result
            if "content" in result:
                # If result is raw content, try to parse as JSON
                try:
                    # Extract JSON from markdown code block if present
                    content = result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]

                    result = json.loads(content.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse SQL generator output: {e}")
                    raise LLMError(f"Failed to parse SQL generator output: {e}")

            # Validate output
            output = SQLGeneratorOutput(**result)

            logger.info(f"SQL generated successfully: {output.sql}")
            return output

        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            raise

    def _format_schema(self, schema_context: Dict[str, Any]) -> str:
        """Format schema context for prompt"""
        tables = schema_context.get("tables", {})
        lines = []

        for table_name, table_info in tables.items():
            columns = table_info.get("columns", [])
            column_strs = [f"  - {col['name']} ({col['type']})" for col in columns]
            lines.append(f"表名: {table_name}")
            lines.append("字段:")
            lines.extend(column_strs)
            lines.append("")

        return "\n".join(lines)

# Global SQL generator instance
sql_generator = SQLGenerator()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/sql_generator.py
git commit -m "feat: add SQL generator agent"
```

---

## Task 12: SQL Repair Agent

**Files:**
- Create: `backend/app/agents/sql_repair.py`

- [ ] **Step 1: Write SQL repair agent**

```python
import json
from typing import Dict, Any

from app.services.llm_service import llm_service
from app.models.schemas import SQLRepairOutput
from app.utils.logger import logger
from app.utils.exceptions import SQLRepairError

SQL_REPAIR_PROMPT = """
你是一个 SQL 修复专家。根据用户问题、原始 SQL、数据库错误信息和 Schema，修复 SQL 语句。

## 用户问题

{question}

## 原始 SQL

{original_sql}

## 数据库错误信息

{error_message}

## 数据库 Schema

{schema_context}

## 要求

1. 分析错误原因
2. 修复 SQL 语句
3. 只输出 JSON 格式

## 输出格式

```json
{{
  "repaired_sql": "修复后的 SQL 语句",
  "repair_reason": "修复原因说明"
}}
```

请严格按照上述格式输出 JSON。
"""

class SQLRepair:
    """SQL repair agent"""

    async def repair(
        self,
        question: str,
        original_sql: str,
        error_message: str,
        schema_context: Dict[str, Any]
    ) -> SQLRepairOutput:
        """
        Repair failed SQL

        Args:
            question: Original natural language question
            original_sql: Original SQL that failed
            error_message: Database error message
            schema_context: Database schema context

        Returns:
            SQLRepairOutput with repaired SQL
        """
        try:
            # Format schema context
            schema_str = self._format_schema(schema_context)

            # Create prompt
            prompt = SQL_REPAIR_PROMPT.format(
                question=question,
                original_sql=original_sql,
                error_message=error_message,
                schema_context=schema_str
            )

            # Call LLM
            system_prompt = "你是一个 SQL 修复专家，根据错误信息修复 SQL。只输出 JSON 格式。"
            result = await llm_service.call_with_retry(prompt, system_prompt)

            # Parse result
            if "content" in result:
                # If result is raw content, try to parse as JSON
                try:
                    # Extract JSON from markdown code block if present
                    content = result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]

                    result = json.loads(content.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse SQL repair output: {e}")
                    raise SQLRepairError(f"Failed to parse SQL repair output: {e}")

            # Validate output
            output = SQLRepairOutput(**result)

            logger.info(f"SQL repaired successfully: {output.repaired_sql}")
            return output

        except Exception as e:
            logger.error(f"SQL repair failed: {e}")
            raise

    def _format_schema(self, schema_context: Dict[str, Any]) -> str:
        """Format schema context for prompt"""
        tables = schema_context.get("tables", {})
        lines = []

        for table_name, table_info in tables.items():
            columns = table_info.get("columns", [])
            column_strs = [f"  - {col['name']} ({col['type']})" for col in columns]
            lines.append(f"表名: {table_name}")
            lines.append("字段:")
            lines.extend(column_strs)
            lines.append("")

        return "\n".join(lines)

# Global SQL repair instance
sql_repair = SQLRepair()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/sql_repair.py
git commit -m "feat: add SQL repair agent"
```

---

## Task 13: Answer Generator Agent

**Files:**
- Create: `backend/app/agents/answer_generator.py`

- [ ] **Step 1: Write answer generator agent**

```python
from typing import Dict, Any, List

from app.services.llm_service import llm_service
from app.utils.logger import logger
from app.utils.exceptions import LLMError

ANSWER_GENERATOR_PROMPT = """
你是一个数据分析助手。根据用户的查询问题和查询结果，生成简洁、准确的自然语言解释。

## 用户问题

{question}

## 查询结果

{query_result}

## 要求

1. 只根据查询结果进行解释，不要编造数据中不存在的信息
2. 对数值结果给出简洁总结
3. 对空结果进行合理说明
4. 保持客观、专业的语气

请直接输出解释文本，不要输出 JSON 格式。
"""

class AnswerGenerator:
    """Answer generation agent"""

    async def generate(
        self,
        question: str,
        query_result: Dict[str, Any]
    ) -> str:
        """
        Generate natural language answer from query result

        Args:
            question: Original natural language question
            query_result: Query execution result

        Returns:
            Natural language explanation
        """
        try:
            # Format query result
            result_str = self._format_result(query_result)

            # Create prompt
            prompt = ANSWER_GENERATOR_PROMPT.format(
                question=question,
                query_result=result_str
            )

            # Call LLM
            system_prompt = "你是一个数据分析助手，根据查询结果生成自然语言解释。"
            result = await llm_service.call_with_retry(prompt, system_prompt)

            # Extract content
            if "content" in result:
                answer = result["content"]
            else:
                answer = str(result)

            logger.info(f"Answer generated successfully")
            return answer

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            raise

    def _format_result(self, query_result: Dict[str, Any]) -> str:
        """Format query result for prompt"""
        if not query_result.get("success"):
            return f"查询失败: {query_result.get('error', 'Unknown error')}"

        columns = query_result.get("columns", [])
        rows = query_result.get("rows", [])

        if not rows:
            return "查询结果为空"

        # Format as table
        lines = ["| " + " | ".join(columns) + " |"]
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

        for row in rows[:10]:  # Limit to first 10 rows
            row_strs = [str(val) if val is not None else "NULL" for val in row]
            lines.append("| " + " | ".join(row_strs) + " |")

        if len(rows) > 10:
            lines.append(f"\n... 共 {len(rows)} 行数据")

        return "\n".join(lines)

# Global answer generator instance
answer_generator = AnswerGenerator()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/answer_generator.py
git commit -m "feat: add answer generator agent"
```

---

## Task 14: LangGraph Agent Workflow

**Files:**
- Create: `backend/app/agents/state.py`
- Create: `backend/app/agents/graph.py`

- [ ] **Step 1: Write agent state**

```python
# backend/app/agents/state.py
from typing import TypedDict, Any, Optional, List, Dict

class AgentState(TypedDict):
    """Agent workflow state"""
    question: str
    schema_context: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    is_sql_safe: bool
    validation_error: Optional[str]
    execution_success: bool
    query_result: Optional[Dict[str, Any]]
    execution_error: Optional[str]
    retry_count: int
    answer: Optional[str]
    optimization_suggestions: List[str]
```

- [ ] **Step 2: Write agent graph**

```python
# backend/app/agents/graph.py
from langgraph.graph import StateGraph, END
from typing import Dict, Any

from app.agents.state import AgentState
from app.agents.sql_generator import sql_generator
from app.agents.sql_repair import sql_repair
from app.agents.answer_generator import answer_generator
from app.db.schema_loader import schema_loader
from app.security.sql_guard import sql_guard
from app.db.query_runner import query_runner
from app.config import settings
from app.utils.logger import logger

class AgentGraph:
    """LangGraph agent workflow"""

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the agent workflow graph"""

        # Create graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("load_schema", self._load_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("repair_sql", self._repair_sql)
        workflow.add_node("generate_answer", self._generate_answer)

        # Set entry point
        workflow.set_entry_point("load_schema")

        # Add edges
        workflow.add_edge("load_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute,
            {
                "execute": "execute_sql",
                "repair": "repair_sql",
                "end": END
            }
        )
        workflow.add_conditional_edges(
            "execute_sql",
            self._should_continue,
            {
                "answer": "generate_answer",
                "repair": "repair_sql",
                "end": END
            }
        )
        workflow.add_edge("repair_sql", "validate_sql")
        workflow.add_edge("generate_answer", END)

        # Compile graph
        return workflow.compile()

    async def _load_schema(self, state: AgentState) -> Dict[str, Any]:
        """Load database schema"""
        logger.info("Loading database schema")
        schema = schema_loader.get_full_schema()
        return {"schema_context": schema}

    async def _generate_sql(self, state: AgentState) -> Dict[str, Any]:
        """Generate SQL from question"""
        logger.info("Generating SQL")
        output = await sql_generator.generate(
            state["question"],
            state["schema_context"]
        )
        return {"generated_sql": output.sql}

    async def _validate_sql(self, state: AgentState) -> Dict[str, Any]:
        """Validate SQL safety"""
        logger.info("Validating SQL safety")
        result = sql_guard.validate(state["generated_sql"])

        return {
            "validated_sql": result["sanitized_sql"],
            "is_sql_safe": result["is_safe"],
            "validation_error": result["reason"]
        }

    async def _execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """Execute SQL query"""
        logger.info("Executing SQL")
        result = query_runner.execute(state["validated_sql"])

        return {
            "execution_success": result["success"],
            "query_result": result,
            "execution_error": result.get("error")
        }

    async def _repair_sql(self, state: AgentState) -> Dict[str, Any]:
        """Repair failed SQL"""
        logger.info("Repairing SQL")
        output = await sql_repair.repair(
            state["question"],
            state["generated_sql"],
            state["execution_error"] or state["validation_error"],
            state["schema_context"]
        )

        return {
            "generated_sql": output.repaired_sql,
            "retry_count": state["retry_count"] + 1
        }

    async def _generate_answer(self, state: AgentState) -> Dict[str, Any]:
        """Generate natural language answer"""
        logger.info("Generating answer")
        answer = await answer_generator.generate(
            state["question"],
            state["query_result"]
        )
        return {"answer": answer}

    def _should_execute(self, state: AgentState) -> str:
        """Determine if SQL should be executed or repaired"""
        if state["is_sql_safe"]:
            return "execute"
        elif state["retry_count"] < settings.SQL_MAX_RETRIES:
            return "repair"
        else:
            return "end"

    def _should_continue(self, state: AgentState) -> str:
        """Determine if execution should continue"""
        if state["execution_success"]:
            return "answer"
        elif state["retry_count"] < settings.SQL_MAX_RETRIES:
            return "repair"
        else:
            return "end"

    async def run(self, question: str) -> Dict[str, Any]:
        """
        Run the agent workflow

        Args:
            question: Natural language question

        Returns:
            Final agent state
        """
        # Initialize state
        initial_state = AgentState(
            question=question,
            schema_context=None,
            generated_sql=None,
            validated_sql=None,
            is_sql_safe=False,
            validation_error=None,
            execution_success=False,
            query_result=None,
            execution_error=None,
            retry_count=0,
            answer=None,
            optimization_suggestions=[]
        )

        # Run graph
        final_state = await self.graph.ainvoke(initial_state)

        return final_state

# Global agent graph instance
agent_graph = AgentGraph()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/state.py backend/app/agents/graph.py
git commit -m "feat: add LangGraph agent workflow"
```

---

## Task 15: API Endpoints

**Files:**
- Create: `backend/app/api/health.py`
- Create: `backend/app/api/schema.py`
- Create: `backend/app/api/query.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Write health endpoint**

```python
# backend/app/api/health.py
from fastapi import APIRouter
from app.models.schemas import SuccessResponse

router = APIRouter()

@router.get("/health", response_model=SuccessResponse)
async def health_check():
    """Health check endpoint"""
    return SuccessResponse(
        code=200,
        message="success",
        data={"status": "healthy"}
    )
```

- [ ] **Step 2: Write schema endpoint**

```python
# backend/app/api/schema.py
from fastapi import APIRouter, HTTPException
from app.models.schemas import SuccessResponse, SchemaResponse
from app.db.schema_loader import schema_loader
from app.utils.logger import logger
from app.utils.exceptions import SchemaLoadError

router = APIRouter()

@router.get("/api/schema", response_model=SuccessResponse)
async def get_schema():
    """Get database schema"""
    try:
        schema = schema_loader.get_full_schema()
        return SuccessResponse(
            code=200,
            message="success",
            data=SchemaResponse(**schema)
        )
    except SchemaLoadError as e:
        logger.error(f"Failed to load schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

- [ ] **Step 3: Write query endpoint**

```python
# backend/app/api/query.py
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    SuccessResponse,
    ErrorResponse
)
from app.agents.graph import agent_graph
from app.utils.logger import logger

router = APIRouter()

@router.post("/api/chat/query", response_model=SuccessResponse)
async def query(request: QueryRequest):
    """Process natural language query"""
    try:
        logger.info(f"Processing query: {request.question}")

        # Run agent workflow
        result = await agent_graph.run(request.question)

        # Prepare response
        response = QueryResponse(
            question=result["question"],
            sql=result.get("validated_sql") or result.get("generated_sql", ""),
            is_sql_safe=result.get("is_sql_safe", False),
            columns=result.get("query_result", {}).get("columns", []),
            rows=result.get("query_result", {}).get("rows", []),
            answer=result.get("answer", ""),
            execution_time_ms=result.get("query_result", {}).get("execution_time_ms", 0),
            retry_count=result.get("retry_count", 0),
            optimization_suggestions=result.get("optimization_suggestions", [])
        )

        return SuccessResponse(
            code=200,
            message="success",
            data=response
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Write main application**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import health, schema, query
from app.utils.logger import logger

# Create FastAPI application
app = FastAPI(
    title="Data Analyst Agent",
    description="Natural language driven database analysis and SQL optimization system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(schema.router)
app.include_router(query.router)

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("Starting Data Analyst Agent API")
    logger.info(f"Database URL: {settings.DATABASE_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("Shutting down Data Analyst Agent API")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/health.py backend/app/api/schema.py backend/app/api/query.py backend/app/main.py
git commit -m "feat: add API endpoints"
```

---

## Task 16: Database Initialization

**Files:**
- Create: `database/init.sql`
- Create: `database/seed_data.py`

- [ ] **Step 1: Write database schema**

```sql
-- database/init.sql
-- Data Analyst Agent Database Schema

-- Regions table
CREATE TABLE IF NOT EXISTS regions (
    region_id INTEGER PRIMARY KEY,
    region_name VARCHAR(50) NOT NULL,
    province VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL
);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    age INTEGER,
    region_id INTEGER,
    register_date DATE,
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category_id INTEGER,
    price DECIMAL(10, 2) NOT NULL,
    cost DECIMAL(10, 2) NOT NULL,
    created_at DATE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Order items table
CREATE TABLE IF NOT EXISTS order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    payment_method VARCHAR(20) NOT NULL,
    payment_status VARCHAR(20) NOT NULL,
    paid_amount DECIMAL(10, 2) NOT NULL,
    paid_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Refunds table
CREATE TABLE IF NOT EXISTS refunds (
    refund_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    refund_amount DECIMAL(10, 2) NOT NULL,
    refund_reason VARCHAR(100),
    refund_date DATE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
```

- [ ] **Step 2: Write seed data script**

```python
# database/seed_data.py
import random
import duckdb
from datetime import datetime, timedelta
from pathlib import Path

# Set random seed for reproducibility
random.seed(42)

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "database.duckdb"

def create_connection():
    """Create database connection"""
    DB_PATH.parent.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH))

def init_database(conn):
    """Initialize database schema"""
    with open(Path(__file__).parent / "init.sql", "r") as f:
        sql = f.read()
    conn.execute(sql)

def generate_regions(conn):
    """Generate region data"""
    regions = [
        (1, "East", "Zhejiang", "Hangzhou"),
        (2, "East", "Shanghai", "Shanghai"),
        (3, "South", "Guangdong", "Guangzhou"),
        (4, "South", "Guangdong", "Shenzhen"),
        (5, "North", "Beijing", "Beijing"),
        (6, "North", "Hebei", "Shijiazhuang"),
        (7, "East", "Jiangsu", "Nanjing"),
        (8, "South", "Fujian", "Fuzhou"),
        (9, "North", "Shandong", "Jinan"),
        (10, "West", "Sichuan", "Chengdu"),
        (11, "West", "Chongqing", "Chongqing"),
        (12, "Central", "Hubei", "Wuhan"),
        (13, "Central", "Hunan", "Changsha"),
        (14, "East", "Anhui", "Hefei"),
        (15, "North", "Tianjin", "Tianjin"),
        (16, "South", "Guangxi", "Nanning"),
        (17, "West", "Yunnan", "Kunming"),
        (18, "North", "Shanxi", "Taiyuan"),
        (19, "East", "Jiangxi", "Nanchang"),
        (20, "Central", "Henan", "Zhengzhou"),
    ]

    conn.executemany(
        "INSERT INTO regions (region_id, region_name, province, city) VALUES (?, ?, ?, ?)",
        regions
    )
    return regions

def generate_categories(conn):
    """Generate category data"""
    categories = [
        (1, "Electronics"),
        (2, "Clothing"),
        (3, "Food"),
        (4, "Home"),
        (5, "Sports"),
        (6, "Books"),
        (7, "Beauty"),
        (8, "Toys"),
    ]

    conn.executemany(
        "INSERT INTO categories (category_id, category_name) VALUES (?, ?)",
        categories
    )
    return categories

def generate_customers(conn, num_customers=1000):
    """Generate customer data"""
    customers = []
    for i in range(1, num_customers + 1):
        customer_id = i
        customer_name = f"Customer_{i}"
        gender = random.choice(["Male", "Female"])
        age = random.randint(18, 65)
        region_id = random.randint(1, 20)
        register_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1095))

        customers.append((
            customer_id, customer_name, gender, age,
            region_id, register_date.strftime("%Y-%m-%d")
        ))

    conn.executemany(
        "INSERT INTO customers (customer_id, customer_name, gender, age, region_id, register_date) VALUES (?, ?, ?, ?, ?, ?)",
        customers
    )
    return customers

def generate_products(conn, num_products=300):
    """Generate product data"""
    products = []
    for i in range(1, num_products + 1):
        product_id = i
        product_name = f"Product_{i}"
        category_id = random.randint(1, 8)
        price = round(random.uniform(10, 1000), 2)
        cost = round(price * random.uniform(0.3, 0.7), 2)
        created_at = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1095))

        products.append((
            product_id, product_name, category_id,
            price, cost, created_at.strftime("%Y-%m-%d")
        ))

    conn.executemany(
        "INSERT INTO products (product_id, product_name, category_id, price, cost, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        products
    )
    return products

def generate_orders(conn, num_orders=10000):
    """Generate order data"""
    orders = []
    for i in range(1, num_orders + 1):
        order_id = i
        customer_id = random.randint(1, 1000)
        order_date = datetime(2022, 1, 1) + timedelta(days=random.randint(0, 1095))
        status = random.choices(
            ["Completed", "Cancelled", "Refunded"],
            weights=[0.8, 0.1, 0.1]
        )[0]
        total_amount = round(random.uniform(50, 5000), 2)

        orders.append((
            order_id, customer_id, order_date.strftime("%Y-%m-%d"),
            status, total_amount
        ))

    conn.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, total_amount) VALUES (?, ?, ?, ?, ?)",
        orders
    )
    return orders

def generate_order_items(conn, orders, num_items_per_order=2):
    """Generate order item data"""
    items = []
    item_id = 1

    for order in orders:
        order_id = order[0]
        num_items = random.randint(1, 5)

        for _ in range(num_items):
            product_id = random.randint(1, 300)
            quantity = random.randint(1, 10)
            unit_price = round(random.uniform(10, 500), 2)

            items.append((
                item_id, order_id, product_id, quantity, unit_price
            ))
            item_id += 1

    conn.executemany(
        "INSERT INTO order_items (item_id, order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
        items
    )
    return items

def generate_payments(conn, orders):
    """Generate payment data"""
    payments = []
    payment_id = 1

    for order in orders:
        order_id = order[0]
        order_status = order[3]

        if order_status == "Completed":
            payment_method = random.choice(["Alipay", "WeChat Pay", "Credit Card", "PayPal"])
            payment_status = "Paid"
            paid_amount = order[4]
            paid_at = datetime.strptime(order[2], "%Y-%m-%d") + timedelta(hours=random.randint(0, 24))

            payments.append((
                payment_id, order_id, payment_method, payment_status,
                paid_amount, paid_at.strftime("%Y-%m-%d %H:%M:%S")
            ))
            payment_id += 1

    conn.executemany(
        "INSERT INTO payments (payment_id, order_id, payment_method, payment_status, paid_amount, paid_at) VALUES (?, ?, ?, ?, ?, ?)",
        payments
    )
    return payments

def generate_refunds(conn, orders):
    """Generate refund data"""
    refunds = []
    refund_id = 1

    for order in orders:
        order_id = order[0]
        order_status = order[3]

        if order_status == "Refunded":
            refund_amount = order[4]
            refund_reason = random.choice([
                "Quality Issue", "Wrong Item", "Not as Described",
                "Changed Mind", "Late Delivery"
            ])
            refund_date = datetime.strptime(order[2], "%Y-%m-%d") + timedelta(days=random.randint(1, 30))

            refunds.append((
                refund_id, order_id, refund_amount, refund_reason,
                refund_date.strftime("%Y-%m-%d")
            ))
            refund_id += 1

    conn.executemany(
        "INSERT INTO refunds (refund_id, order_id, refund_amount, refund_reason, refund_date) VALUES (?, ?, ?, ?, ?)",
        refunds
    )
    return refunds

def main():
    """Main function to generate seed data"""
    print("Generating seed data...")

    conn = create_connection()

    try:
        # Initialize database
        init_database(conn)
        print("Database schema created")

        # Generate data
        regions = generate_regions(conn)
        print(f"Generated {len(regions)} regions")

        categories = generate_categories(conn)
        print(f"Generated {len(categories)} categories")

        customers = generate_customers(conn)
        print(f"Generated {len(customers)} customers")

        products = generate_products(conn)
        print(f"Generated {len(products)} products")

        orders = generate_orders(conn)
        print(f"Generated {len(orders)} orders")

        items = generate_order_items(conn, orders)
        print(f"Generated {len(items)} order items")

        payments = generate_payments(conn, orders)
        print(f"Generated {len(payments)} payments")

        refunds = generate_refunds(conn, orders)
        print(f"Generated {len(refunds)} refunds")

        print("Seed data generation completed!")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add database/init.sql database/seed_data.py
git commit -m "feat: add database schema and seed data"
```

---

## Task 17: Frontend Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "data-analyst-agent-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.3.8",
    "element-plus": "^2.4.4",
    "axios": "^1.6.2",
    "echarts": "^5.4.3",
    "pinia": "^2.1.7"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.5.2",
    "vite": "^5.0.10"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

- [ ] **Step 3: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Data Analyst Agent</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 5: Create App.vue**

```vue
<template>
  <div id="app">
    <el-container>
      <el-header>
        <h1>Data Analyst Agent</h1>
      </el-header>
      <el-main>
        <Home />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import Home from './views/Home.vue'
</script>

<style>
#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}

.el-header {
  background-color: #409eff;
  color: white;
  text-align: center;
  line-height: 60px;
}

.el-header h1 {
  margin: 0;
  font-size: 24px;
}
</style>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/src/main.js frontend/src/App.vue
git commit -m "feat: add frontend setup"
```

---

## Task 18: Frontend Components

**Files:**
- Create: `frontend/src/api/agent.js`
- Create: `frontend/src/stores/query.js`
- Create: `frontend/src/components/QueryInput.vue`
- Create: `frontend/src/components/SQLPanel.vue`
- Create: `frontend/src/components/ResultTable.vue`
- Create: `frontend/src/components/ChartPanel.vue`
- Create: `frontend/src/components/AnswerPanel.vue`
- Create: `frontend/src/views/Home.vue`

- [ ] **Step 1: Create API client**

```javascript
// frontend/src/api/agent.js
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

export async function queryAgent(question) {
  const response = await api.post('/chat/query', { question })
  return response.data.data
}

export async function getSchema() {
  const response = await api.get('/schema')
  return response.data.data
}

export async function validateSQL(sql) {
  const response = await api.post('/sql/validate', { sql })
  return response.data.data
}

export async function executeSQL(sql) {
  const response = await api.post('/sql/execute', { sql })
  return response.data.data
}
```

- [ ] **Step 2: Create Pinia store**

```javascript
// frontend/src/stores/query.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { queryAgent } from '@/api/agent'

export const useQueryStore = defineStore('query', () => {
  const question = ref('')
  const loading = ref(false)
  const result = ref(null)
  const error = ref(null)
  const history = ref([])

  async function submitQuestion() {
    if (!question.value.trim()) return

    loading.value = true
    error.value = null

    try {
      const response = await queryAgent(question.value)
      result.value = response

      history.value.unshift({
        question: question.value,
        result: response,
        timestamp: new Date()
      })
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  function clearResult() {
    result.value = null
    error.value = null
  }

  return {
    question,
    loading,
    result,
    error,
    history,
    submitQuestion,
    clearResult
  }
})
```

- [ ] **Step 3: Create QueryInput component**

```vue
<template>
  <div class="query-input">
    <el-input
      v-model="store.question"
      type="textarea"
      :rows="3"
      placeholder="请输入您的数据分析问题，例如：统计2024年每个月的销售额"
      @keyup.ctrl.enter="store.submitQuestion"
    />
    <el-button
      type="primary"
      :loading="store.loading"
      @click="store.submitQuestion"
    >
      开始分析
    </el-button>
  </div>
</template>

<script setup>
import { useQueryStore } from '@/stores/query'

const store = useQueryStore()
</script>

<style scoped>
.query-input {
  margin-bottom: 20px;
}

.query-input .el-button {
  margin-top: 10px;
}
</style>
```

- [ ] **Step 4: Create SQLPanel component**

```vue
<template>
  <div class="sql-panel" v-if="store.result">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>生成的 SQL</span>
          <el-tag :type="store.result.is_sql_safe ? 'success' : 'danger'">
            {{ store.result.is_sql_safe ? '安全' : '不安全' }}
          </el-tag>
        </div>
      </template>
      <pre><code>{{ store.result.sql }}</code></pre>
    </el-card>
  </div>
</template>

<script setup>
import { useQueryStore } from '@/stores/query'

const store = useQueryStore()
</script>

<style scoped>
.sql-panel {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}

code {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 14px;
}
</style>
```

- [ ] **Step 5: Create ResultTable component**

```vue
<template>
  <div class="result-table" v-if="store.result && store.result.columns.length > 0">
    <el-card>
      <template #header>
        <span>查询结果 ({{ store.result.rows.length }} 行)</span>
      </template>
      <el-table :data="tableData" border stripe>
        <el-table-column
          v-for="column in store.result.columns"
          :key="column"
          :prop="column"
          :label="column"
        />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useQueryStore } from '@/stores/query'

const store = useQueryStore()

const tableData = computed(() => {
  if (!store.result) return []

  return store.result.rows.map(row => {
    const obj = {}
    store.result.columns.forEach((column, index) => {
      obj[column] = row[index]
    })
    return obj
  })
})
</script>

<style scoped>
.result-table {
  margin-bottom: 20px;
}
</style>
```

- [ ] **Step 6: Create ChartPanel component**

```vue
<template>
  <div class="chart-panel" v-if="store.result && store.result.rows.length > 0">
    <el-card>
      <template #header>
        <span>数据可视化</span>
      </template>
      <div ref="chartRef" style="width: 100%; height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as echarts from 'echarts'
import { useQueryStore } from '@/stores/query'

const store = useQueryStore()
const chartRef = ref(null)
let chart = null

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value)
  }
})

watch(() => store.result, (newResult) => {
  if (newResult && chart) {
    updateChart(newResult)
  }
}, { deep: true })

function updateChart(result) {
  const option = {
    title: {
      text: '查询结果'
    },
    tooltip: {},
    xAxis: {
      type: 'category',
      data: result.rows.slice(0, 20).map(row => row[0])
    },
    yAxis: {
      type: 'value'
    },
    series: [{
      name: result.columns[1] || '数据',
      type: 'bar',
      data: result.rows.slice(0, 20).map(row => row[1])
    }]
  }

  chart.setOption(option)
}
</script>

<style scoped>
.chart-panel {
  margin-bottom: 20px;
}
</style>
```

- [ ] **Step 7: Create AnswerPanel component**

```vue
<template>
  <div class="answer-panel" v-if="store.result && store.result.answer">
    <el-card>
      <template #header>
        <span>分析结果</span>
      </template>
      <p>{{ store.result.answer }}</p>
      <div class="meta-info">
        <el-tag>执行时间: {{ store.result.execution_time_ms }}ms</el-tag>
        <el-tag v-if="store.result.retry_count > 0">
          重试次数: {{ store.result.retry_count }}
        </el-tag>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { useQueryStore } from '@/stores/query'

const store = useQueryStore()
</script>

<style scoped>
.answer-panel {
  margin-bottom: 20px;
}

.meta-info {
  margin-top: 15px;
}

.meta-info .el-tag {
  margin-right: 10px;
}
</style>
```

- [ ] **Step 8: Create Home view**

```vue
<template>
  <div class="home">
    <el-row :gutter="20">
      <el-col :span="16">
        <QueryInput />
        <SQLPanel />
        <ResultTable />
        <ChartPanel />
        <AnswerPanel />
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>历史记录</span>
          </template>
          <div v-if="store.history.length === 0" class="empty-history">
            暂无历史记录
          </div>
          <div v-else class="history-list">
            <div
              v-for="(item, index) in store.history"
              :key="index"
              class="history-item"
              @click="loadHistory(item)"
            >
              <p class="question">{{ item.question }}</p>
              <p class="time">{{ formatTime(item.timestamp) }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useQueryStore } from '@/stores/query'
import QueryInput from '@/components/QueryInput.vue'
import SQLPanel from '@/components/SQLPanel.vue'
import ResultTable from '@/components/ResultTable.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import AnswerPanel from '@/components/AnswerPanel.vue'

const store = useQueryStore()

function loadHistory(item) {
  store.question = item.question
  store.result = item.result
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleString('zh-CN')
}
</script>

<style scoped>
.home {
  padding: 20px;
}

.empty-history {
  color: #909399;
  text-align: center;
  padding: 20px;
}

.history-item {
  padding: 10px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
}

.history-item:hover {
  background-color: #f5f7fa;
}

.history-item .question {
  margin: 0 0 5px 0;
  font-size: 14px;
}

.history-item .time {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
</style>
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/agent.js frontend/src/stores/query.js frontend/src/components/QueryInput.vue frontend/src/components/SQLPanel.vue frontend/src/components/ResultTable.vue frontend/src/components/ChartPanel.vue frontend/src/components/AnswerPanel.vue frontend/src/views/Home.vue
git commit -m "feat: add frontend components"
```

---

## Task 19: Docker Configuration

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine as build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: Create docker-compose.yml**

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=duckdb:///./data/database.duckdb
      - QWEN_API_KEY=${QWEN_API_KEY}
      - QWEN_API_URL=${QWEN_API_URL}
      - QWEN_MODEL=${QWEN_MODEL}
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  data:
  logs:
```

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml
git commit -m "feat: add Docker configuration"
```

---

## Task 20: Documentation and README

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Create README.md**

```markdown
# Data Analyst Agent

一个基于自然语言驱动的数据库分析与 SQL 优化系统。

## 核心功能

- 自然语言转 SQL 查询
- SQL 安全校验（防止危险操作）
- SQL 自动修复（字段错误、表名错误等）
- 查询结果自然语言解释
- SQL 优化建议
- 数据可视化

## 技术栈

### 后端
- Python 3.10+
- FastAPI
- LangGraph
- SQLGlot
- DuckDB
- Qwen API

### 前端
- Vue 3
- Element Plus
- ECharts
- Vite

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/data-analyst-agent.git
cd data-analyst-agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置 QWEN_API_KEY
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m database.seed_data
uvicorn app.main:app --reload
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5. 访问应用

- 前端: http://localhost:3000
- API 文档: http://localhost:8000/docs

## Docker 部署

```bash
docker-compose up -d
```

## 示例问题

- 统计 2024 年每个月的销售额
- 找出销售额最高的前 10 个商品
- 计算不同地区的复购率
- 分析各商品类别的退款率

## 项目结构

```
data-analyst-agent/
├── backend/          # 后端服务
├── frontend/         # 前端应用
├── database/         # 数据库脚本
├── docs/             # 项目文档
└── docker-compose.yml
```

## 开发文档

- [开发文档 v0.2](docs/data_analyst_agent_开发文档_v_0_2.md)
- [数据库设计](docs/database_design_md.md)

## 许可证

MIT License
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Database
*.duckdb
*.duckdb.wal

# Logs
*.log
logs/

# Environment
.env
.env.local
.env.*.local

# Node.js
node_modules/
dist/
.npm

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml
```

- [ ] **Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: add README and gitignore"
```

---

## Self-Review Checklist

After writing this plan, I've reviewed it against the spec:

1. **Spec coverage:**
   - ✅ Natural language to SQL conversion
   - ✅ SQL safety validation (SQL Guard)
   - ✅ SQL execution with error handling
   - ✅ SQL repair mechanism
   - ✅ Answer generation
   - ✅ Database schema design
   - ✅ API endpoints
   - ✅ Frontend components
   - ✅ Docker deployment

2. **Placeholder scan:**
   - ✅ No TBD or TODO placeholders
   - ✅ Complete code in every step
   - ✅ Exact file paths specified

3. **Type consistency:**
   - ✅ Consistent naming conventions
   - ✅ Matching method signatures across tasks

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2024-12-23-data-analyst-agent-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
