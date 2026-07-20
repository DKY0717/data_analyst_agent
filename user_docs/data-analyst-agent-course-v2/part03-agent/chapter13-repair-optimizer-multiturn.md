# 第13章 SQL Repair、优化与多轮上下文
> 本章预计 2 小时，理解失败恢复和会话继承。
## 13.1 学习目标
> 能解释 Repair 输入、重新校验、规则优化和安全会话摘要。
## 13.2 前置知识
> 需要完成第12章状态路由。
## 13.3 为什么需要这一模块
> 模型 SQL 可能因字段或方言失败，用户也会连续追问；系统需要恢复能力但不能牺牲安全。
## 13.4 输入、输出与依赖
> Repair 输入原 SQL、错误和 Schema；多轮输入最近安全成功轮次；输出修复 SQL、建议或上下文摘要。
## 13.5 执行流程
```text
Execution Error → Repair → SQL Guard → Permission → Execute
Success → Safe Summary → Next Question Context
```
## 13.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Repair | `backend/app/agents/sql_repair.py` |
| Optimizer | `backend/app/agents/sql_optimizer.py` |
| Session | `backend/app/agents/session_store.py` |
## 13.7 关键代码理解
> 修复 SQL 不是可信输出，必须重新走 Guard 和权限；上下文不保存完整 rows，也不写入失败或越权轮次。
## 13.8 最小动手运行
```bash
pytest backend/tests/test_sql_repair.py backend/tests/test_sql_optimizer.py backend/tests/test_session_store.py -q
```
## 13.9 故障注入实验
> 用错误列触发确定性执行失败，观察 Repair 后重新校验；使用 Fake LLM 避免费用。
## 13.10 调试路径与常见误判
> HTTP 重试、SQL Repair 和多轮重新提问具有不同计数与安全语义。
## 13.11 独立编码练习
> 为“按地区拆一下”设计最小上下文摘要，禁止包含完整结果行。
## 13.12 测试或评测验证
> 对照 Repair 故障注入 case，解释意图保持检查。
## 13.13 面试复述题
> 为什么危险 SQL 或权限拒绝不能进入 Repair？
## 13.14 掌握度检查与下一章
> 能解释恢复与安全终止的边界。下一部分建立系统性安全治理。
