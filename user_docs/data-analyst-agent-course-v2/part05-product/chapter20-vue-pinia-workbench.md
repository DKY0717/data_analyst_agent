# 第20章 Vue、Pinia 与分析工作台

> 本章预计 1～2 小时，学习前端如何把长请求和多类证据组织成单一状态流。无需启动真实模型。

## 20.1 学习目标

> 能追踪 QueryInput→Home→Pinia→API→结果面板；解释 ref/computed、sessionId、SSE/同步切换、取消、澄清、历史和状态清理。

## 20.2 前置知识

> 了解 JavaScript Promise、`async/await`、Vue 组合式 API 和第19章接口契约。

## 20.3 为什么需要这一模块

> 同一请求同时有 loading、stage、progress、result、error、clarification 和 abort task。若组件各自保存副本，连续查询会显示旧结果或无法取消；Pinia 提供单一事实来源。

## 20.4 输入、输出与依赖

| Store 状态 | 作用 |
|---|---|
| question/sessionId | 当前问题与多轮身份 |
| loading/stage/progress | 请求生命周期 |
| result/error | 互斥最终状态 |
| history/favorites | 本地使用记录 |
| useStreaming/abortController | 传输方式与取消 |
| schemaTables | 辅助 Schema 面板 |

## 20.5 执行流程

```text
QueryInput emit → Home.handleSubmit → store.submitQuestion
  → clear old result/error → SSE or axios
  → progress updates → final normalized result
  → history + panels → finally reset loading/controller
```

## 20.6 当前代码地图

| 内容 | 路径 |
|---|---|
| 页面编排 | `frontend/src/views/Home.vue` |
| Query Store | `frontend/src/stores/query.js` |
| Auth Store | `frontend/src/stores/auth.js` |
| API client | `frontend/src/api/agent.js` |
| 输入组件 | `frontend/src/components/QueryInput.vue` |
| Store 测试 | `frontend/tests/stores/query.test.js` |

## 20.7 关键代码理解

### 20.7.1 sessionId 是工作台级状态

> Store 初始化一次随机 sessionId，连续提问复用它，使后端能恢复上下文和澄清；清页面结果不等于清后端会话。若需要“新会话”功能，应显式轮换 ID。

### 20.7.2 提交前清旧状态

> `submitQuestion` 先设置 loading、清 error 与 result，避免新请求期间显示旧答案。finally 无论成功、失败或取消都重置 controller 与 progress。

### 20.7.3 澄清为何走同步接口

> 当前条件是 streaming 且没有 clarification 才走 SSE；澄清提交携带 clarificationId/candidateId 走普通 query，后端 SessionStore 恢复原问题。

### 20.7.4 取消是用户操作，不是普通失败

> AbortError 只把 stage 设为已取消，不写失败历史；其他异常进入 error 并记录失败。前端仍依赖后端断连取消，双方都要正确收尾。

### 20.7.5 Schema 加载是辅助路径

> `loadSchema()` 失败被隔离，不阻断主查询。这是产品降级边界：辅助面板失败不应让核心 Agent 失效。

## 20.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
npm run test --prefix frontend -- --run tests/stores/query.test.js
npm run build --prefix frontend
```

## 20.9 故障注入实验

> Fake API 第一请求成功、第二请求拒绝，确认第二次开始时旧 result 已清空且 finally 复位 loading；再取消 SSE，确认 AbortError 不写错误历史。

## 20.10 调试路径与常见误判

> 先看 Network 请求/响应，再看 API parser，再看 Store 的 result/error/loading，最后看组件 props。页面空白可能是结果被清空、computed 条件不成立或组件生命周期问题，不一定是后端无数据。

## 20.11 独立编码练习

> 增加“新建会话”设计草案：取消当前请求、生成新 sessionId、清结果但是否保留 favorites/history要明确。为状态转换写测试后再考虑实现。

## 20.12 测试或评测验证

> 验证成功、错误、取消、连续查询、澄清、history上限、favorite持久化、Schema失败隔离与后端响应契约。

```bash
pytest backend/tests/test_frontend_query_response_contract.py -q
npm run test --prefix frontend -- --run
```

## 20.13 面试复述题

> 1. 为什么 Agent 前端适合集中式 Store？
>
> 2. sessionId 与一次 HTTP 请求有什么区别？
>
> 3. 如何避免连续查询显示旧结果？

## 20.14 掌握度检查与下一章

> 能从事件追到 Store 和组件；能手写 submit 状态机；能区分取消与失败。下一章学习图表、导出和审计界面。
