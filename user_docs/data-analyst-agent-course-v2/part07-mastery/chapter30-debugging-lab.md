# 第30章 实战二：端到端调试实验室
> 本章预计 1～2 小时，练习在没有答案提示时定位一次“结果为空”故障。
## 30.1 学习目标
> 能用证据判断问题属于前端、接口、Intent、Grounding、SQL、安全、数据库还是模型供应商。
## 30.2 前置知识
> 已完成前六部分，并能运行后端测试和前端构建。
## 30.3 为什么需要这一模块
> Agent 链路长，表面现象常与根因相距多个节点；固定调试顺序比随机改 Prompt 更可靠。
## 30.4 输入、输出与依赖
> 输入是一条失败请求及其 request ID、响应和日志；输出是最小复现、根因、修复范围与回归证据。
## 30.5 执行流程
```text
reproduce → classify boundary → inspect state/events → isolate dependency → prove cause → regress
```
## 30.6 当前代码地图
| 内容 | 路径 |
|---|---|
| API 边界 | `backend/app/api/query.py` |
| Agent 图 | `backend/app/agents/graph.py` |
| 执行器 | `backend/app/db/query_runner.py` |
| 追踪 | `backend/app/services/tracing.py` |
| 前端 Store | `frontend/src/stores/query.js` |
## 30.7 关键代码理解
> 调试先保存输入与现象，再沿结构化状态缩小范围。只有证明某节点输入正确、输出错误后，才应修改该节点。
## 30.8 最小动手运行
```bash
pytest backend/tests/test_query_api.py backend/tests/test_agent_graph.py backend/tests/test_tracing.py -q
```
## 30.9 故障注入实验
> 选择一种可恢复注入：错误列名、数据库超时或 SSE 中断。记录预期节点、实际错误分类和用户可见响应。
## 30.10 调试路径与常见误判
> 建议顺序是浏览器 Network、API 响应、审计/轨迹、Intent、Grounding、SQL Guard、执行结果、前端状态。切勿在无法复现时同时改多层。
## 30.11 独立编码练习
> 输出一份调试报告，必须包含最小复现、排除过的假设、根因证据、最小修复与回归用例。
## 30.12 测试或评测验证
> 修复后先跑新增回归测试，再跑相邻模块测试，最后按风险决定是否执行完整后端和前端验证。
## 30.13 面试复述题
> 用户说“Agent 给了空结果”，你会按什么顺序定位？
## 30.14 掌握度检查与下一章
> 能在不乱改代码的情况下定位到单一边界。下一章从零重建最小 Agent。
