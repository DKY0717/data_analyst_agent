# 第五章：组装完整的 Agent 工作流

> 本章目标：用 LangGraph 把所有组件串联成完整的 pipeline。
>
> 完成本章后，你将拥有一个完整的"自然语言 → SQL → 查询 → 答案"系统。

## 5.1 什么是 LangGraph

> LangGraph 是一个工作流编排框架。你可以把它想象成一个**流程图引擎**：
>
> - **节点**：一个处理步骤（比如"生成 SQL"）
> - **边**：节点之间的连线（比如"生成 SQL → 校验 SQL"）
> - **条件边**：根据结果走不同路径（比如"校验通过 → 执行，校验失败 → 终止"）
> - **状态**：所有节点共享的数据字典
>
> 代码执行时，LangGraph 从入口节点开始，沿着边依次执行每个节点，直到到达终点。

## 5.2 安装 LangGraph

```bash
cd backend
pip install langgraph==0.2.0
```

> 更新 `backend/requirements.txt`，**用以下内容替换整个文件**：

```text
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.2
python-dotenv==1.0.0
duckdb==0.9.2
httpx==0.25.2
sqlglot==20.0.0
langgraph==0.2.0
```

## 5.3 定义状态

> 状态是所有节点共享的数据字典。每个节点读取需要的字段，写入产出的字段。
>
> 创建 `backend/app/agents/` 目录和 `__init__.py`：

```bash
mkdir backend/app/agents
New-Item -Path "backend/app/agents/__init__.py" -ItemType File -Force
```

> 创建 `backend/app/agents/state.py`：

```python
from typing import TypedDict, Any, Optional, Dict, List


class AgentState(TypedDict):
    """Agent 工作流共享状态

    所有节点通过这个字典通信。
    每个节点读取需要的字段，写入产出的字段。
    """
    # 输入
    question: str

    # Schema
    schema_context: Optional[Dict[str, Any]]

    # SQL 处理
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    is_sql_safe: bool
    validation_error: Optional[str]

    # 执行结果
    execution_success: bool
    query_result: Optional[Dict[str, Any]]
    execution_error: Optional[str]
    retry_count: int

    # 输出
    answer: Optional[str]
```

> **为什么用 TypedDict 而不是普通字典？**
>
> TypedDict 让 LangGraph 知道每个字段的类型，可以做类型检查。同时它仍然是普通字典，访问和修改都很方便。

## 5.4 定义查询执行器

> SQL 校验通过后，需要一个执行器来运行 SQL 并返回结果。
>
> 创建 `backend/app/db/query_runner.py`：

```python
import time
from typing import Dict, Any
from .connection import db_connection
from ..config import settings


class QueryRunner:
    """SQL 查询执行器"""

    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.SQL_TIMEOUT

    def execute(self, sql: str) -> Dict[str, Any]:
        """执行 SQL 查询

        Returns:
            {
                "success": True/False,
                "columns": ["列名1", "列名2"],
                "rows": [[值1, 值2], ...],
                "execution_time_ms": 15,
                "error": "错误信息" (仅失败时)
            }
        """
        start_time = time.time()

        try:
            with db_connection.get_session() as conn:
                result = conn.execute(sql)
                columns = [desc[0] for desc in result.description] if result.description else []
                rows = [list(row) for row in result.fetchall()]
                execution_time_ms = int((time.time() - start_time) * 1000)

                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "execution_time_ms": execution_time_ms,
                    "row_count": len(rows)
                }
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "execution_time_ms": execution_time_ms,
                "error": str(e),
                "error_type": type(e).__name__
            }


# 全局单例
query_runner = QueryRunner()
```

## 5.5 构建工作流图

> 创建 `backend/app/agents/graph.py`，这是整个系统的核心：

```python
from typing import Dict, Any
from langgraph.graph import StateGraph, END

from .state import AgentState
from ..db.schema_loader import schema_loader
from ..db.query_runner import query_runner
from ..security.sql_guard import sql_guard
from ..services.llm_service import llm_client
from ..config import settings


class AgentGraph:
    """LangGraph Agent 工作流"""

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建工作流图

        流程:
        load_schema → generate_sql → validate_sql → execute_sql
                                              ↓           ↓
                                          (不安全)    (失败,可重试)
                                              ↓           ↓
                                             END    repair_sql → validate_sql
                                         execute_sql → (成功) → generate_answer → END
        """
        workflow = StateGraph(AgentState)

        # 注册节点
        workflow.add_node("load_schema", self._load_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_sql", self._execute_sql)
        workflow.add_node("repair_sql", self._repair_sql)
        workflow.add_node("generate_answer", self._generate_answer)

        # 入口
        workflow.set_entry_point("load_schema")

        # 固定边
        workflow.add_edge("load_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_edge("generate_answer", END)

        # 条件边：校验后
        workflow.add_conditional_edges(
            "validate_sql",
            self._should_execute,
            {"execute": "execute_sql", "end": END}
        )

        # 条件边：执行后
        workflow.add_conditional_edges(
            "execute_sql",
            self._should_continue,
            {"answer": "generate_answer", "repair": "repair_sql", "end": END}
        )

        # 修复后回到校验
        workflow.add_edge("repair_sql", "validate_sql")

        return workflow.compile()

    # ---- 节点实现 ----

    async def _load_schema(self, state: AgentState) -> Dict[str, Any]:
        """加载数据库 Schema"""
        schema = schema_loader.get_full_schema()
        return {"schema_context": schema}

    async def _generate_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 生成 SQL"""
        result = await llm_client.generate_sql(
            state["question"],
            str(state["schema_context"])
        )
        return {"generated_sql": result["sql"]}

    async def _validate_sql(self, state: AgentState) -> Dict[str, Any]:
        """校验 SQL 安全性"""
        result = sql_guard.validate(state["generated_sql"])
        return {
            "validated_sql": result["sanitized_sql"],
            "is_sql_safe": result["is_safe"],
            "validation_error": result.get("reason")
        }

    async def _execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """执行 SQL 查询"""
        result = query_runner.execute(state["validated_sql"])
        return {
            "execution_success": result["success"],
            "query_result": result,
            "execution_error": result.get("error")
        }

    async def _repair_sql(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 修复失败的 SQL"""
        result = await llm_client.repair_sql(
            state["generated_sql"],
            state["execution_error"],
            str(state["schema_context"])
        )
        return {
            "generated_sql": result["repaired_sql"],
            "retry_count": state["retry_count"] + 1
        }

    async def _generate_answer(self, state: AgentState) -> Dict[str, Any]:
        """调用 LLM 生成自然语言答案"""
        answer = await llm_client.generate_answer(
            state["question"],
            state["validated_sql"],
            state["query_result"]
        )
        return {"answer": answer}

    # ---- 条件判断 ----

    def _should_execute(self, state: AgentState) -> str:
        """SQL 安全则执行，否则终止"""
        return "execute" if state["is_sql_safe"] else "end"

    def _should_continue(self, state: AgentState) -> str:
        """执行成功→生成答案，失败且可重试→修复，否则→终止"""
        if state["execution_success"]:
            return "answer"
        if state["retry_count"] < settings.SQL_MAX_RETRIES:
            return "repair"
        return "end"

    async def run(self, question: str) -> AgentState:
        """运行完整的 Agent 工作流"""
        initial_state: AgentState = {
            "question": question,
            "schema_context": None,
            "generated_sql": "",
            "validated_sql": "",
            "is_sql_safe": False,
            "validation_error": None,
            "execution_success": False,
            "query_result": None,
            "execution_error": None,
            "retry_count": 0,
            "answer": None,
        }
        return await self.graph.ainvoke(initial_state)


# 全局单例（延迟初始化）
_agent_graph = None

def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = AgentGraph()
    return _agent_graph
```

> **流程图解释：**
>
> ```text
> load_schema（加载表结构）
>     ↓
> generate_sql（LLM 生成 SQL）
>     ↓
> validate_sql（安全校验）
>     ↓
> ├── 安全 → execute_sql → 成功 → generate_answer → END
> └── 不安全 → END
>                  ↓
>              失败 → repair_sql → validate_sql（回到校验）
> ```
>
> **为什么修复后要回到校验？**
>
> 防止 LLM 在修复过程中生成不安全的 SQL。比如原始 SQL 是安全的 SELECT，修复后可能变成了 DELETE。

## 5.6 创建查询 API 端点

> **替换** `backend/app/main.py` 的全部内容为：

```python
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional

from .config import settings, ensure_directories
from .db.schema_loader import schema_loader
from .agents.graph import get_agent_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    yield


app = FastAPI(
    title="Data Analyst Agent",
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/schema")
async def get_schema():
    try:
        schema = schema_loader.get_full_schema()
        return {"code": 200, "data": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/query")
async def query(request: QueryRequest):
    """核心接口：自然语言 → SQL → 查询 → 答案"""
    try:
        result = await get_agent_graph().run(request.question)

        query_result = result.get("query_result") or {}

        return {
            "code": 200,
            "data": {
                "question": result["question"],
                "sql": result.get("validated_sql") or result.get("generated_sql") or "",
                "is_sql_safe": result.get("is_sql_safe", False),
                "columns": query_result.get("columns", []),
                "rows": query_result.get("rows", []),
                "answer": result.get("answer") or "处理失败，请换个问法。",
                "execution_time_ms": query_result.get("execution_time_ms", 0),
                "retry_count": result.get("retry_count", 0),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 5.7 测试完整流程

> 重启后端（在项目根目录下）：

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```

> 访问 http://localhost:8000/docs，找到 `POST /api/chat/query`，点击 "Try it out"，输入：

```json
{
  "question": "查询销售额最高的前5个商品"
}
```

> 你应该看到类似响应：

```json
{
  "code": 200,
  "data": {
    "question": "查询销售额最高的前5个商品",
    "sql": "SELECT p.product_name, SUM(oi.quantity * oi.unit_price) AS sales FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.product_name ORDER BY sales DESC LIMIT 5",
    "is_sql_safe": true,
    "columns": ["product_name", "sales"],
    "rows": [
      ["Laptop", 123456.00],
      ["Smartphone", 98765.00],
      ...
    ],
    "answer": "销售额最高的前5个商品分别是 Laptop、Smartphone、Tablet、Smartwatch 和 Headphones...",
    "execution_time_ms": 15,
    "retry_count": 0
  }
}
```

> **恭喜！你的数据分析 Agent 已经可以工作了。**

## 5.8 本章小结

> 你完成了：
> - 定义了 AgentState（所有节点共享的状态）
> - 实现了查询执行器
> - 用 LangGraph 构建了完整的工作流图
> - 创建了核心查询 API
> - 端到端测试通过：自然语言 → SQL → 查询 → 答案
>
> 下一章我们将构建前端界面。
