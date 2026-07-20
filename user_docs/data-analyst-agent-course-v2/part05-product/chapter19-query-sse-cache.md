# 第19章 查询 API、SSE 进度与缓存

> 本章预计 1～2 小时，学习同一 Agent 如何服务同步与流式请求。测试全部离线。

## 19.1 学习目标

> 能解释同步/SSE 契约、心跳、分块解析、断连取消、最终结果、匿名缓存条件、精确/相似匹配、TTL 和降级结果不缓存。

## 19.2 前置知识

> 已理解 FastAPI、AgentGraph、session、认证、答案失败隔离和异步任务取消。

## 19.3 为什么需要这一模块

> Agent 可能持续几十秒；同步接口适合简单客户端，SSE 让浏览器持续看到阶段。取消必须停止后台任务，避免断开后继续花模型额度。缓存只能复用上下文和权限完全无关的稳定结果。

## 19.4 输入、输出与依赖

| 接口 | 输出 |
|---|---|
| `POST /api/chat/query` | 一次 `SuccessResponse<QueryResponse>` |
| `POST /api/chat/query/stream` | progress、result/error、`[DONE]` 与注释心跳 |

> 两条接口最终使用同一 `QueryResponse` 字段。SSE 的 progress 只是过程消息，只有 result 事件代表业务结果。

## 19.5 执行流程

```text
sync: validate/auth → eligible cache lookup → graph → response → optional cache write
SSE:  validate/auth → graph task + queue → progress/heartbeat → result → optional cache write
      client disconnect/abort → cancel and await graph task
```

> 当前 SSE 路由不读取缓存，只在满足条件且成功时写入；同步路由才会先查询缓存。这是当前源码事实，不应把两条路径描述成完全相同。

## 19.6 当前代码地图

| 内容 | 路径 |
|---|---|
| 同步/SSE | `backend/app/api/query.py` |
| Progress | `backend/app/agents/progress_notifier.py` |
| SQLite cache | `backend/app/services/query_cache.py` |
| 前端 parser | `frontend/src/api/agent.js` |
| runtime 测试 | `backend/tests/test_query_stream_runtime.py` |

## 19.7 关键代码理解

### 19.7.1 缓存允许条件

> 只有 current_user 为空、无 clarification_id、无 session_id 才允许共享 question-only 缓存。认证请求避免跨角色结果泄露；会话和澄清依赖上下文，不能按问题文本复用；answer_error 降级结果不写缓存。
>
> 当前前端 Store 默认始终生成 sessionId，所以标准前端查询不会使用共享缓存。这不是缓存失效，而是安全/多轮优先的结果。

### 19.7.2 相似缓存不是向量语义

> Cache 先用规范化问题 SHA256 精确匹配，再把中文按字、英文数字按词做集合，用 Jaccard 阈值0.85匹配。它只是轻量文本相似度，可能把字面相近但筛选不同的问题混淆；因此范围被严格限制。

### 19.7.3 SSE 心跳与取消

> 队列空闲15秒发送 `: heartbeat`；每次等待检查 request disconnect。finally 中取消并 await pipeline task，避免悬空 coroutine。响应头关闭代理缓冲和缓存。

### 19.7.4 前端必须处理分块

> `reader.read()` 的 chunk 不等于一条事件。客户端保留 buffer、按换行拆分，只解析 `data: ` 行；流结束却无 result 时明确失败，不能把最后 progress 当成功。

## 19.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_query_api.py backend/tests/test_query_stream_runtime.py backend/tests/test_query_cache.py -q
```

## 19.9 故障注入实验

> 用 Fake Graph 长时间等待，客户端 AbortController 取消，断言任务被取消、无 result、无缓存写入。再构造两个字面高度相似但年份不同的问题，观察轻量相似缓存的风险。

## 19.10 调试路径与常见误判

> 依次检查 HTTP status、Content-Type、Nginx buffering、心跳、progress、result、`[DONE]`、AbortError 和后端 task cleanup。收到进度不代表完成；缓存 hit 也不代表重新执行了权限链。

## 19.11 独立编码练习

> 写一个 Mini SSE parser，输入任意分块字符串，统计 progress 并只在 result 后 resolve。为半条 JSON、多个事件同 chunk、error、无 final result 写测试。

## 19.12 测试或评测验证

> 覆盖同步契约、SSE 分块、心跳、断连取消、认证/会话绕过缓存、精确/相似命中、TTL、容量和降级不缓存。

## 19.13 面试复述题

> 1. 为什么不能让所有查询共享缓存？
>
> 2. 当前同步与 SSE 缓存行为有什么差别？
>
> 3. 为什么断开浏览器后还要 await 被取消任务？

## 19.14 掌握度检查与下一章

> 能准确画出两条请求路径；能解释默认前端为何不命中共享缓存；能实现分块 parser。下一章进入 Vue/Pinia。
