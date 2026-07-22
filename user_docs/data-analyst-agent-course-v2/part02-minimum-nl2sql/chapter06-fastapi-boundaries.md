# 第6章 FastAPI 请求与异常边界

> 本章预计 1～2 小时，理解 HTTP 如何安全进入 Python 业务逻辑。练习使用 TestClient/Fake Agent，不调用真实模型。

## 6.1 学习目标
> 能解释应用组装、路由、请求体、依赖注入、限流、业务状态、响应模型和异常边界；能从一次 HTTP 失败定位到正确层。

## 6.2 前置知识
> 需要理解 HTTP 方法、JSON 和第2章的 Pydantic 模型。

## 6.3 为什么需要这一模块
> API 是不可信外部输入进入系统的第一道契约边界，也是前端、认证和 Agent 的连接点。

## 6.4 输入、输出与依赖
| 输入来源 | Python 参数 | 作用 |
|---|---|---|
| HTTP 请求上下文 | `request: Request` | 限流、断连检测 |
| JSON body | `body: QueryRequest` | 问题、会话与澄清 |
| FastAPI dependency | `current_user = Depends(...)` | 可选身份 |

> 输出外层为 `SuccessResponse`，业务数据为 `QueryResponse`；校验错误与系统异常则走稳定错误结构。HTTP 状态、外层 code 和 Agent `status` 是三个不同维度。

## 6.5 执行流程
```text
HTTP → middleware/rate limit → dependency + Pydantic
  → cache decision → AgentGraph → QueryResponse → HTTP
```

## 6.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 应用 | `backend/app/main.py` |
| 查询路由 | `backend/app/api/query.py` |
| Schema 路由 | `backend/app/api/schema.py` |
| 模型 | `backend/app/models/schemas.py` |
| 异常 | `backend/app/utils/exceptions.py` |
| API 测试 | `backend/tests/test_query_api.py` |

## 6.7 关键代码理解
### 6.7.1 声明式边界

```python
@router.post("/api/chat/query", response_model=SuccessResponse)
async def query(
    request: Request,
    body: QueryRequest,
    current_user: AuthUser | None = Depends(get_current_user),
):
    ...
```

> 装饰器决定路径和方法；类型声明决定数据来源与校验；`response_model` 约束序列化结果。空问题在进入 Agent 前由 Pydantic 拒绝。

### 6.7.2 业务状态不是 HTTP 状态

> `completed` 表示完成；`blocked` 表示安全阻断；`clarification_required` 表示需要用户补充；`clarification_expired` 表示澄清上下文失效。后两者是可预期业务分支，不应全部伪装成 500。

### 6.7.3 边界层只做协调

> 路由负责认证上下文、缓存条件、调用图和响应转换，不负责拼 SQL 或重新实现 Guard。重复业务逻辑会让同步与 SSE 接口行为漂移。

### 6.7.4 异常与 Secret

> 未知异常对外返回通用信息和 request ID；完整堆栈只留在受控日志。数据库诊断、Authorization、API Key 与完整供应商响应不能进入客户端。

## 6.8 最小动手运行
```bash
pytest backend/tests/test_query_api.py -q
```

> 工作目录：项目根目录。网络/真实模型：不需要，测试替换 Agent 与依赖。

## 6.9 故障注入实验
> 用 TestClient 发送 `{ "question": "" }`，预期 422，并让 Fake Agent 记录调用次数为 0；随后发送合法问题确认调用一次。实验不修改服务配置。

## 6.10 调试路径与常见误判
> 按顺序看：Network 的 URL/方法/状态；422 的字段位置；401/403 的身份；429 的限流；2xx 内 `data.status`；5xx 的 request ID 与服务日志。200 可能仍是澄清或阻断，前端必须读业务状态。

## 6.11 独立编码练习
> 为只读版本信息接口设计路径、响应模型与两个测试：成功契约、内部实现多返回字段时响应过滤。说明为何它不应依赖 LLM。

## 6.12 测试或评测验证
> 对比 Fake Agent API 测试与 `test_agent_graph.py`：前者证明 HTTP 契约和转换，后者证明图路由；任何一个都不能单独证明真实模型质量。

```bash
pytest backend/tests/test_query_api.py backend/tests/test_frontend_query_response_contract.py -q
```

## 6.13 面试复述题
> 1. 为什么 API 要保留 `blocked`、`clarification_required` 与系统失败的区别？
>
> 2. FastAPI 如何知道 `body` 和 `current_user` 来自不同位置？
>
> 3. 为什么同步路由和 SSE 路由应复用同一 Agent 业务逻辑？

## 6.14 掌握度检查与下一章
> 能预测空问题、无权限、澄清和未知异常的不同结果；能指出路由职责边界。下一章进入统一 LLM 客户端。
