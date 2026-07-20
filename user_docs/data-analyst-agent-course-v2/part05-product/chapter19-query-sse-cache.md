# 第19章 查询 API、SSE 进度与缓存
> 本章预计 1～2 小时，学习同一条 Agent 工作流如何服务同步查询和流式查询。
## 19.1 学习目标
> 能说明同步接口、SSE 事件、取消信号与匿名查询缓存之间的关系。
## 19.2 前置知识
> 已理解 FastAPI 边界、完整 Agent 图和会话状态。
## 19.3 为什么需要这一模块
> Agent 调用可能持续数秒；同步响应简单可靠，SSE 则让用户看到阶段进度，缓存可减少安全可复用请求的成本。
## 19.4 输入、输出与依赖
> 输入是问题、会话与澄清信息；输出是统一查询结果或 `progress/result/error` 事件流，依赖 Agent 图、认证和查询缓存。
## 19.5 执行流程
```text
POST request → auth/rate limit → optional cache → graph → response or SSE events
```
## 19.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 查询路由 | `backend/app/api/query.py` |
| 进度通知 | `backend/app/agents/progress_notifier.py` |
| 查询缓存 | `backend/app/services/query_cache.py` |
| 前端请求 | `frontend/src/api/agent.js` |
## 19.7 关键代码理解
> 缓存只用于无用户、无会话、无澄清的请求，避免把带权限或上下文的结果跨用户复用。流式接口最终仍返回与同步接口一致的业务结果。
## 19.8 最小动手运行
```bash
pytest backend/tests/test_query_api.py backend/tests/test_query_stream_runtime.py backend/tests/test_query_cache.py -q
```
## 19.9 故障注入实验
> 在流处理中主动取消客户端请求，观察生成任务是否结束，并确认不会缓存未完成结果。
## 19.10 调试路径与常见误判
> 先区分 HTTP 连接失败、SSE 解析失败和 Agent 内部失败；收到进度不代表最终结果已经成功。
## 19.11 独立编码练习
> 为 SSE 客户端实现事件计数，并在最终事件到达时校验结果结构。
## 19.12 测试或评测验证
> 同时验证同步/流式契约、缓存命中、权限请求绕过缓存和取消清理。
## 19.13 面试复述题
> 为什么本项目没有让所有查询都进入缓存？
## 19.14 掌握度检查与下一章
> 能画出两种请求路径并解释缓存边界。下一章进入 Vue 状态工作台。
