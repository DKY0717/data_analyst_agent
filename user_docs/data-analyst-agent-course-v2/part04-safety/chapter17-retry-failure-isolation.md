# 第17章 重试、错误分类与失败隔离
> 本章预计 2 小时，学习不同失败的不同处理方式。
## 17.1 学习目标
> 能区分传输重试、SQL Repair、答案失败和不可重试安全错误。
## 17.2 前置知识
> 需要理解 LLM 服务、Graph 和 QueryRunner。
## 17.3 为什么需要这一模块
> 把所有错误都重试会放大费用和延迟，也可能让危险或越权请求进入 Repair。
## 17.4 输入、输出与依赖
> 输入是异常、状态和已完成阶段；输出是重试、降级、终止或保留部分结果。
## 17.5 执行流程
```text
Error → Classify → Transport Retry / SQL Repair / Partial Success / Stop
```
## 17.6 当前代码地图
| 内容 | 路径 |
|---|---|
| LLM | `backend/app/services/llm_service.py` |
| Exceptions | `backend/app/utils/exceptions.py` |
| Graph | `backend/app/agents/graph.py` |
## 17.7 关键代码理解
> SQL 已执行成功而答案失败时应隔离答案节点，避免丢失 SQL 和结果证据；空 content 必须形成明确失败。
## 17.8 最小动手运行
```bash
pytest backend/tests/test_llm_service.py backend/tests/test_agent_graph.py -q
```
## 17.9 故障注入实验
> 用 Fake LLM 让答案节点失败，观察查询证据是否保留。
## 17.10 调试路径与常见误判
> 多次 HTTP 尝试可能属于一次逻辑调用；不要用 API 尝试数代替 Agent Repair 次数。
## 17.11 独立编码练习
> 为四种错误写出“可重试、可修复、可降级、必须终止”分类表。
## 17.12 测试或评测验证
> 检查答案失败隔离和危险阻断不进入 Repair 的测试。
## 17.13 面试复述题
> 为什么失败隔离比简单捕获所有异常更难？
## 17.14 掌握度检查与下一章
> 能为错误选择正确路径。下一章学习审计和可观测证据。
