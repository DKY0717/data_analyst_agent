# 第20章 Vue、Pinia 与分析工作台
> 本章预计 1～2 小时，学习前端如何把后端结果组织成可操作的分析工作台。
## 20.1 学习目标
> 能追踪一次提问从组件、Store、API 到结果面板的状态变化。
## 20.2 前置知识
> 了解 JavaScript 异步调用、Vue 组合式 API 和第19章接口契约。
## 20.3 为什么需要这一模块
> Agent 返回 SQL、表格、图表、意图、优化与审计等多类信息，需要统一状态源避免组件各自维护冲突状态。
## 20.4 输入、输出与依赖
> 输入是用户问题和认证状态；输出是加载、进度、澄清、成功或错误视图，依赖 Vue 3、Pinia、路由和 API 封装。
## 20.5 执行流程
```text
QueryInput → query store → API/SSE → normalized state → result panels
```
## 20.6 当前代码地图
| 内容 | 路径 |
|---|---|
| 页面编排 | `frontend/src/views/Home.vue` |
| 查询状态 | `frontend/src/stores/query.js` |
| 认证状态 | `frontend/src/stores/auth.js` |
| 查询输入 | `frontend/src/components/QueryInput.vue` |
| API 客户端 | `frontend/src/api/agent.js` |
## 20.7 关键代码理解
> Store 是请求生命周期的单一事实来源；组件读取派生状态并发出用户动作，不应各自复制一份结果对象。
## 20.8 最小动手运行
```bash
cd frontend
npm run build
```
## 20.9 故障注入实验
> 让后端返回非 200 业务错误，检查 loading 是否复位、旧结果是否被误当成新结果。
## 20.10 调试路径与常见误判
> 先看浏览器 Network，再看 Store，最后看组件渲染；页面空白不一定是接口没有返回。
## 20.11 独立编码练习
> 增加一个只读的“最后一次请求耗时”状态，并在页面展示。
## 20.12 测试或评测验证
> 运行前端构建，并用后端响应契约测试防止字段漂移。
```bash
pytest backend/tests/test_frontend_query_response_contract.py -q
```
## 20.13 面试复述题
> 为什么 Agent 前端适合用集中式 Store 管理状态？
## 20.14 掌握度检查与下一章
> 能定位输入、网络、状态和渲染四层问题。下一章学习图表、导出与审计界面。
