# 第十四章 SSE、缓存、可观测性与成本统计

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 14.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释普通 JSON 请求与 SSE 流式请求的差异；
> 2. 说明进度回调、心跳和客户端取消如何协作；
> 3. 理解为什么认证用户和多轮查询不能复用匿名问题缓存；
> 4. 读懂 LLM 调用轨迹中的 Token、耗时、尝试次数和成本字段；
> 5. 说明 Prompt 版本和 A/B 测试如何帮助回归；
> 6. 识别可观测性数据中不能记录的敏感内容。

## 14.2 问题场景：功能正确还不够

> 一个完整查询可能经过意图解析、Grounding、Schema 加载、SQL 生成、校验、权限、执行、优化和答案生成。如果前端只在最后收到一个 JSON，用户会长时间面对空白页面，也无法知道失败发生在哪一步。
>
> 产品化能力要同时解决三个问题：给用户实时反馈，避免重复计算，给维护者足够的请求级证据。SSE、缓存和可观测性分别承担这三个方向，但都不能改变安全判定。

## 14.3 SSE 流式查询

### 14.3.1 进度队列和回调

```python
progress_queue: asyncio.Queue = asyncio.Queue()

def on_progress_callback(stage: str, progress: int):
    progress_queue.put_nowait({"stage": stage, "progress": progress})
```

> `query_stream()` 创建一个队列，把 AgentGraph 节点通过 `on_progress` 发出的阶段事件转发给 `event_generator()`。业务节点不需要知道 HTTP 协议，只调用统一的进度回调。

### 14.3.2 SSE 事件格式

```text
data: {"type":"progress","stage":"生成 SQL 查询...","progress":65}

data: {"type":"result","data":{...}}

data: [DONE]
```

> SSE 使用以空行分隔的 `data:` 事件。前端逐行读取并解析 JSON，进度事件更新状态，最终结果事件填充完整响应，`[DONE]` 表示流结束。

### 14.3.3 心跳和断开

> `_wait_for_stream_event()` 在队列空闲时发送注释心跳 `: heartbeat`，避免代理把长时间无数据的连接判定为失效；同时检查 `request.is_disconnected()`。客户端主动取消后，`_cancel_pipeline_task()` 会取消并等待后台 Agent task，避免用户已经离开后还继续消耗模型额度。

## 14.4 SSE 与普通查询的选择

| 模式 | 优点 | 适合场景 |
|---|---|---|
| `/api/chat/query` | 结构简单、客户端容易调用 | 脚本、测试、短查询 |
| `/api/chat/query/stream` | 及时展示阶段、支持心跳和取消 | Web 工作台、较长查询 |

> 两个端点都应使用同一套 AgentGraph 和 QueryResponse 契约，不能因为是 SSE 就跳过认证、权限或审计。SSE 只是传输方式，不是安全模式。

## 14.5 查询缓存

> `query_cache` 以规范化问题作为匿名单轮查询的键，保存成功结果并设置 TTL/容量边界。缓存命中可以避免重复调用 LLM 和数据库，但缓存也可能复用错误身份的数据，因此路由明确限制：认证用户、带 `session_id` 或带澄清请求的查询不使用 question-only 共享缓存。

```python
cache_allowed = current_user is None \
    and not body.clarification_id \
    and not body.session_id
```

> 这个判断体现了“缓存键必须包含影响结果的所有上下文”。如果角色、行过滤或会话历史会改变结果，就不能只用问题文本作为键。

## 14.6 缓存的失效边界

> 查询结果可能因数据库写入、策略变化、语义配置或模型版本变化而失效。当前缓存更适合演示和短期重复查询；生产系统需要结合数据更新事件、策略版本和 Prompt 版本设计更细的失效键。
>
> 缓存命中也应该保留稳定的响应形状，让前端知道这是缓存结果；不能把缓存命中当成重新经过 Guard 和权限的证据。当前实现只对满足匿名单轮条件的成功结果写入缓存。

## 14.7 LLM 调用可观测性

```python
_llm_calls: ContextVar[List[Dict[str, Any]]] = ContextVar("llm_calls", default=[])
```

> `ContextVar` 为每个异步请求保存独立调用列表，避免并发请求互相污染。每次模型调用记录：阶段、模型、输入 Token、输出 Token、总 Token、延迟、尝试次数、是否成功、错误类型和可选成本。

```json
{
  "stage": "generate_sql",
  "model": "mimo-v2.5-pro",
  "input_tokens": 800,
  "output_tokens": 120,
  "total_tokens": 920,
  "latency_ms": 1800,
  "attempt_count": 1,
  "estimated_cost": null,
  "success": true
}
```

> 价格未配置时成本保持 `null`，`cost_available` 为 false。Token 和耗时是观测数据，不等于结果正确性；正确性还要由评测和业务基准判断。

## 14.8 可观测性隐私边界

> 轨迹不保存 Prompt、Authorization、API Key、完整模型响应或敏感客户值。OpenTelemetry 追踪也应该使用去字面量后的 SQL 结构指纹、语句类型和物理表名，而不是把完整 SQL 写入 span。
>
> “能定位问题”与“保存所有原文”不是一回事。阶段名称、错误类型和结构指纹通常足够判断故障位置；需要详细诊断时，应在受控的内部链路按最小范围保留。

## 14.9 Prompt 版本和 A/B 测试

> Prompt Registry 为同一 Prompt 名称递增版本，保存内容哈希和创建时间。SQL Generator 还可以根据 A/B 配置路由到某个 Prompt 版本，并记录变体的成功率、延迟、Token 和成本摘要。

```text
问题
  ↓
ABTestRegistry.route("generate_sql", question)
  ↓
选择 Prompt 版本
  ↓
调用模型并记录结果
```

> A/B 测试不是“随机挑一个看起来更好的 Prompt”。要定义成功指标、样本、失败类别和停止条件，并避免把不同用户权限或不同业务问题混在同一个结论里。

## 14.10 端到端观测流程

```text
前端提交
  ↓
SSE 推送节点进度
  ↓
AgentGraph 记录审计事件和 LLM calls
  ↓
QueryRunner 记录执行耗时和行数
  ↓
API 返回 QueryResponse + AuditReport
  ↓
前端展示答案、SQL、指标、审计和优化建议
```

## 14.11 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/api/query.py` | 普通查询和 SSE 端点 | 队列、心跳、取消、响应组装 |
| `backend/app/services/query_cache.py` | 查询缓存 | TTL、容量和键 |
| `backend/app/services/llm_observability.py` | LLM 调用轨迹 | ContextVar、Token、成本 |
| `backend/app/services/tracing.py` | 节点追踪 | 脱敏属性和阶段 |
| `backend/app/services/prompt_registry.py` | Prompt 版本 | 哈希、注册和回滚 |
| `backend/app/services/ab_test.py` | A/B 实验 | 路由、记录和汇总 |
| `frontend/src/stores/query.js` | 前端进度状态 | SSE、取消和结果合并 |

## 14.12 动手验证

> 运行缓存、追踪和观测测试：

```bash
pytest backend/tests/test_query_cache.py backend/tests/test_tracing.py backend/tests/test_llm_observability.py -q
```

> 前端构建也会检查 SSE Store 和 API 模块能否被正确打包：

```bash
npm run build --prefix frontend
```

> 真实 SSE 体验需要启动后端和前端；如果模型端点不可用，仍然可以通过前端测试和后端 SSE 契约测试验证事件解析、取消和错误边界。

## 14.13 常见错误

### SSE 没有最终结果

> 检查服务端是否发送了 `type=result` 和 `[DONE]`，以及前端是否在流结束前处理了最后一段缓冲区。只有进度事件而没有结果时，Store 应报告流协议错误。

### 客户端取消后模型仍在调用

> 只关闭浏览器读取器不一定会取消服务端任务。后端必须在 `finally` 中取消并等待 Agent task；节点也不能吞掉取消信号后继续执行。

### 缓存返回了其他角色的数据

> 检查缓存键是否包含用户、角色和行过滤上下文。当前实现对认证用户和多轮请求关闭匿名共享缓存。

### 成本显示为 0

> 如果价格没有配置，正确状态是 `estimated_cost: null` 和 `cost_available: false`，不能把未知成本伪装成零成本。

## 14.14 本章小结

> SSE 改善等待体验，缓存减少重复工作，LLM 观测说明调用成本，Prompt Registry 和 A/B 记录帮助判断版本变化。它们都属于产品化的“可见性和效率”层，不能替代 Intent Guard、SQL Guard 和数据权限；任何缓存或流式路径都必须复用同一安全工作流。

## 14.15 练习

1. 画出一次 SSE 查询从节点进度到前端 `loadingStage` 的传递路径。
2. 说明为什么带 `session_id` 的查询不能使用问题文本共享缓存。
3. 为一个 Prompt 版本计算内容哈希，观察只改变空格是否会产生新版本。
4. 构造一个成本价格只配置输入、不配置输出的场景，判断观测结果。
5. 找出后端取消任务和前端 `AbortController` 之间的对应关系。

## 14.16 下一章衔接

> 后端已经可以实时返回结果和观测证据，下一章会学习如何用 Vue、Pinia、Axios、ECharts 和多个展示组件把这些数据变成可操作的分析工作台。
