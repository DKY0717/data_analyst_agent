# 第2章 Python、异步与类型模型

> 本章预计 1～2 小时，把已有 Python 基础连接到项目真实实现。所有练习均可离线完成。

## 2.1 学习目标

> 能读懂包与相对导入、类型标注、Pydantic 模型、`async`/`await`、可选值、默认工厂和 FastAPI 依赖注入；能区分 JSON、字典、模型实例与协程。

## 2.2 前置知识

> 需要会定义函数和类，理解列表、字典、异常。无需先掌握事件循环内部实现。

## 2.3 为什么需要这一模块

> 项目同时传递外部 JSON、内部 TypedDict 状态和 Pydantic 响应。若把它们混为一谈，就容易漏校验、直接修改共享默认值，或忘记 `await` 而得到 coroutine 对象。

## 2.4 输入、输出与依赖

| Python 形式 | 项目用途 | 运行时约束 |
|---|---|---|
| `dict[str, Any]` | 灵活的内部/外部数据 | 字段拼错不一定立即报错 |
| `TypedDict` | Agent State 静态提示 | 主要帮助类型检查，不做完整运行时校验 |
| Pydantic `BaseModel` | API 与 LLM 结构化契约 | 实例化时校验和转换 |
| `Optional[str]` | 字段可为字符串或 `None` | 不代表一定有默认值 |
| `async def` | 定义协程函数 | 调用后先得到协程对象 |
| `await` | 等待协程结果 | 只能位于异步上下文 |

## 2.5 执行流程

```text
HTTP JSON
  → QueryRequest 运行时校验
  → async query()
  → await AgentGraph.run(...)
  → QueryResponse 校验
  → model_dump() / JSON
```

> FastAPI 根据函数签名识别请求体与依赖。`body: QueryRequest` 来自 JSON，`current_user = Depends(get_current_user)` 来自认证依赖，两者来源不同但都在调用路由函数前准备好。

## 2.6 当前代码地图

| 概念 | 路径 | 关注符号 |
|---|---|---|
| API 模型 | `backend/app/models/schemas.py` | `QueryRequest`、`QueryResponse`、`AuditReport` |
| Agent 状态 | `backend/app/agents/state.py` | `AgentState` |
| 配置对象 | `backend/app/config.py` | `Settings`、`settings` |
| 异步路由 | `backend/app/api/query.py` | `query`、`query_stream` |
| 异步工作流 | `backend/app/agents/graph.py` | `run` 与节点函数 |

## 2.7 关键代码理解

### 2.7.1 包、模块与相对导入

> `backend/app/main.py` 是模块，`backend/app` 因包含 `__init__.py` 而是包。`from .config import settings` 的点表示从当前包导入，因此启动模块时通常使用 `uvicorn app.main:app` 并把工作目录放在 `backend`。

### 2.7.2 Pydantic 是运行时边界

```python
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=128)
```

> `...` 表示必填；`None` 表示可省略；长度约束在请求进入业务流程前执行。类型提示本身通常不会阻止错误值，Pydantic 才会产生结构化校验错误。

### 2.7.3 为什么使用 default_factory

```python
events: list[AuditEvent] = Field(default_factory=list)
```

> 每个模型实例都获得自己的新列表，避免多个请求意外共享一个可变默认对象。看到列表、字典或集合默认值时都要检查这一点。

### 2.7.4 async 不等于并行

```python
async def query(...):
    result = await agent_graph.run(...)
```

> 调用 `query()` 会创建协程；执行到 `await` 时，若底层操作正在等待，事件循环才有机会处理其他任务。CPU 密集计算和同步数据库调用不会因为外层写了 `async` 自动变快。

### 2.7.5 结构化失败同样属于契约

> `ErrorResponse` 有 `error_code`、`error_type`、`message`、`details` 和 `request_id`。用户可读信息与内部异常堆栈应分离，避免把数据库细节或凭据暴露给客户端。

## 2.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
python -c "from backend.app.models.schemas import QueryRequest; q=QueryRequest(question='统计销售额'); print(q.model_dump())"
```

> 如果使用项目的 backend 虚拟环境，也可在 `backend` 目录按包入口导入：

```bash
cd backend
python -c "from app.models.schemas import QueryRequest; print(QueryRequest(question='统计销售额'))"
```

## 2.9 故障注入实验

> 工作目录：项目根目录。下面故意传空问题，预期得到 `ValidationError`；命令不会修改文件。

```bash
python -c "from backend.app.models.schemas import QueryRequest; QueryRequest(question='')"
```

> 记录错误中的字段位置、错误类型和约束，再把问题改成非空值确认恢复。不要用删除 `min_length` 的方式让错误“消失”。

## 2.10 调试路径与常见误判

| 现象 | 常见原因 | 检查方式 |
|---|---|---|
| `ModuleNotFoundError` | 工作目录/包入口错误 | 看 `Get-Location` 与导入前缀 |
| 输出 `<coroutine object ...>` | 忘记 `await` | 查调用函数是否为 `async def` |
| 422 | 请求模型校验失败 | 看响应 `loc/type/msg` |
| `NoneType` 错误 | 可选字段未经分支处理 | 查 `Optional` 和默认值 |
| 请求间数据串扰 | 共享可变对象 | 查列表/字典默认值和全局状态 |

> `asyncio.create_task()` 会让任务独立运行，也引入取消和异常回收责任。第19章的 SSE 路由专门处理这类生命周期，不要随意把普通 `await` 改成后台任务。

## 2.11 独立编码练习

> 在个人练习文件中定义 `MiniQueryResult`：必填 `question`，状态仅允许 `completed/failed`，`sql` 可选，`rows` 使用默认工厂。分别构造合法值、空问题、非法状态和两个实例，证明列表不共享。

## 2.12 测试或评测验证

> 工作目录：项目根目录。网络/真实模型：不需要。API 测试使用替身隔离完整模型调用。

```bash
pytest backend/tests/test_query_api.py -q
```

> 阅读测试时标记 Arrange（准备请求/替身）、Act（调用接口）、Assert（状态码和字段）。如果只记住测试数量，就还没有理解契约。

## 2.13 面试复述题

> 1. Pydantic 为什么不只是类型提示？
>
> 2. `async def`、调用协程函数和 `await` 各发生了什么？
>
> 3. 为什么审计事件列表使用 `default_factory=list`？

## 2.14 掌握度检查与下一章

> 能解释 JSON→模型→字典的转换；能预测空问题的错误；能指出 Query API 中请求体、依赖和 `await`。完成后进入 SQL 与电商业务模型。
