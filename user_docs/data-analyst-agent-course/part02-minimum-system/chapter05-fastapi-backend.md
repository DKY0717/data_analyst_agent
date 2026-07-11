# 第五章 搭建 FastAPI 后端

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 5.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 说明 `FastAPI` 应用实例和路由之间的关系；
> 2. 读懂项目的生命周期函数、CORS 和限流初始化；
> 3. 理解 Pydantic 请求模型为什么是 API 的边界；
> 4. 区分存活检查、就绪检查和业务查询接口；
> 5. 使用 API 文档和测试验证后端契约；
> 6. 解释异常为什么不能把数据库或密钥原文直接返回给客户端。

## 5.2 问题场景

> 前一章的数据库能力还只能由 Python 内部调用。要让 Vue 前端或 curl 使用它，需要一个 HTTP 服务：客户端发送 JSON，后端校验输入，调用业务模块，再返回稳定的 JSON。
>
> FastAPI 在这里不是“所有逻辑的容器”。它主要负责请求边界、路由、依赖注入和响应模型；数据库、LLM 和 Agent 仍然放在各自模块。分层的目的，是让 HTTP 细节不会渗透到核心业务代码中。

## 5.3 应用入口

```python
app = FastAPI(
    title="Data Analyst Agent",
    description="自然语言驱动的数据库分析与 SQL 优化系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(schema.router)
app.include_router(query.router)
app.include_router(auth_router.router)
```

> `app` 是 ASGI 应用对象。`include_router()` 把不同业务模块的端点注册到同一个应用中。启动命令 `uvicorn app.main:app --reload` 的含义是：导入 `app.main` 模块，并使用其中名为 `app` 的对象。

## 5.4 生命周期与启动准备

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_tracing()
    logger.info("Data Analyst Agent API 启动")
    yield
    logger.info("Data Analyst Agent API 关闭")
```

> `yield` 前的代码在应用开始接收请求前执行，`yield` 后的代码在应用关闭时执行。当前实现会创建数据和日志目录、初始化追踪，并记录启动日志。
>
> 这段代码没有在导入模块时立刻连接数据库或调用 LLM。延迟初始化可以减少测试导入副作用，也让应用启动失败的位置更容易定位。

## 5.5 配置、CORS 与限流

### 5.5.1 配置不应散落在路由中

> `backend/app/config.py` 的 `Settings` 集中读取环境变量，例如数据库后端、LLM URL、SQL 超时和 CORS 白名单。路由通过 `settings` 使用已经解析好的值，不需要自己解析字符串或布尔值。

```text
QWEN_API_KEY=你的密钥
QWEN_API_URL=https://example.com/v1/chat/completions
QWEN_MODEL=mimo-v2.5-pro
SQL_TIMEOUT=30
SANDBOX_MODE=true
```

> API Key 只应该存在于环境变量或本地未提交的 `.env` 中。教程、日志和提交记录都不能出现真实密钥。

### 5.5.2 CORS 是浏览器边界

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> CORS 控制浏览器是否允许某个来源读取响应，不等于身份认证。允许前端域名访问 API，并不会自动授予用户数据库权限；认证和权限由后续模块负责。

### 5.5.3 限流初始化

> `setup_rate_limit(app)` 为查询接口安装慢速限流器。限流是资源保护手段，不能替代 SQL 超时、结果行数限制或用户权限检查。

## 5.6 Pydantic 请求与响应契约

```python
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=128)
    clarification_id: Optional[str] = Field(None, max_length=128)
```

> `QueryRequest` 在进入业务函数之前限制问题长度，并为多轮会话和主动澄清保留结构化字段。这样业务代码可以假设 `question` 已经是非空字符串，而不必在每个节点重复做相同检查。
>
> `QueryResponse` 使用 `extra="forbid"`，表示响应中出现未声明字段时会被拒绝。这会尽早暴露前后端字段漂移，而不是让前端默默显示空白。

## 5.7 路由职责

| 路由模块 | 端点示例 | 职责 |
|---|---|---|
| `health.py` | `/health`、`/health/readiness` | 进程存活和依赖就绪状态 |
| `schema.py` | `/api/schema` | 返回数据库结构 |
| `query.py` | `/api/chat/query` | 执行完整分析工作流 |
| `auth_router.py` | `/api/auth/demo-login` | 本地演示或密码认证 |

> 健康检查不应该通过一次完整的 LLM 查询来判断服务是否活着。`/health` 主要说明进程能响应，`/health/readiness` 进一步检查数据库连接、核心业务表和演示数据。两者给容器编排系统的含义不同。

## 5.8 健康检查的验证思路

```python
@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

> 存活检查越简单越好；如果它依赖外部 LLM，模型暂时不可用时容器会被误判为“进程死亡”。就绪检查才适合报告数据库和关键业务数据是否准备好。

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/readiness
```

## 5.9 异常边界

> 查询路由会记录稳定的错误消息，并向客户端返回通用提示，而不是把异常对象原文直接放进 HTTP 响应。数据库错误原文可能包含表名、文件路径、SQL 片段或凭据相关信息；这些信息应该只在受控的内部诊断链路使用。

```python
except Exception:
    logger.error("查询处理失败")
    raise HTTPException(status_code=500, detail="查询处理失败，请稍后重试")
```

> 这里的通用错误不是为了隐藏所有问题，而是把“用户可见消息”和“内部诊断信息”分开。后续 SQL Repair 会在受控范围内使用错误类型和必要诊断，审计报告只保留稳定摘要。

## 5.10 请求流程

```text
HTTP 请求
  ↓
FastAPI 路由匹配
  ↓
Pydantic 校验 QueryRequest
  ↓
依赖注入认证用户和限流器
  ↓
调用 Schema、Health 或 AgentGraph
  ↓
构造 QueryResponse / SuccessResponse
  ↓
JSON 返回客户端
```

## 5.11 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/main.py` | 创建应用并注册路由 | lifespan、中间件、router |
| `backend/app/config.py` | 环境配置解析 | 布尔值、枚举、路径和安全默认值 |
| `backend/app/models/schemas.py` | API 数据模型 | 输入边界、响应字段、严格契约 |
| `backend/app/api/health.py` | 健康和就绪检查 | 依赖检查与返回状态 |
| `backend/app/api/schema.py` | Schema 查询接口 | 调用 SchemaLoader |
| `backend/app/utils/exceptions.py` | 领域异常 | 区分数据库、LLM、Schema 错误 |

## 5.12 动手验证

> 先运行确定性测试：

```bash
pytest backend/tests/test_health.py backend/tests/test_schema_loader.py -q
```

> 再启动服务并打开自动生成的 API 文档：

```bash
cd backend
uvicorn app.main:app --reload
```

> 浏览器访问 `http://127.0.0.1:8000/docs`，确认可以看到 `/health`、`/health/readiness` 和 `/api/schema`。如果没有配置 LLM Key，健康和 Schema 接口仍然应该可以工作，因为它们不需要调用模型。

## 5.13 常见错误

### `Error loading ASGI app`

> 这通常是启动目录错误。命令中的 `app.main:app` 需要在 `backend` 目录执行，或者通过正确的 Python 模块路径启动。先确认当前目录中存在 `app/main.py`。

### 浏览器跨域失败

> 检查前端实际来源是否在 `CORS_ALLOW_ORIGINS` 中。端口 `3000`、`5173` 和 `8000` 并不等价；CORS 只比较完整的来源。

### 请求字段被拒绝

> 查看 Pydantic 的 422 响应，确认 JSON 字段名、字符串长度和类型。不要为了让旧前端“凑合工作”而取消 `extra="forbid"`，应该同步修正调用方契约。

## 5.14 本章小结

> FastAPI 层把外部 HTTP 世界和内部业务模块连接起来，但不应该承担 SQL 生成或数据库权限判断。应用入口负责组装，Pydantic 负责契约，路由负责调度，生命周期负责启动和关闭准备，异常边界负责避免敏感信息外泄。

## 5.15 练习

1. 给 `/health` 增加一个不泄露密钥的版本字段，并补充测试。
2. 追踪 `/api/schema` 的请求从路由到数据库查询的完整调用链。
3. 临时把 `question` 的最大长度改为 10，观察超长请求的响应。
4. 说明为什么就绪检查失败时，进程仍可能是存活的。

## 5.16 下一章衔接

> 现在后端可以接收请求，但还没有“理解问题”的能力。下一章会在这个 HTTP 应用之外单独学习 OpenAI-compatible LLM 客户端，理解请求体、重试、结构化输出和 Secret 边界。
