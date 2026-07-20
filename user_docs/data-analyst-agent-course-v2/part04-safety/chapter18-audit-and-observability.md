# 第18章 安全审计与 LLM 可观测性
> 本章预计 1～2 小时，学习如何证明系统做过什么。
## 18.1 学习目标
> 能解释审计事件、权限摘要、LLM 调用轨迹和脱敏边界。
## 18.2 前置知识
> 需要理解完整 Agent 节点和安全路径。
## 18.3 为什么需要这一模块
> 没有结构化证据时，安全阻断、权限改写和模型成本只能靠口头描述。
## 18.4 输入、输出与依赖
> 输入是各节点事件和调用轨迹；输出是请求级 audit_report 和离线安全报告。
## 18.5 执行流程
```text
Node Events + Permission + LLM Trace → Audit Summary → API/Report
```
## 18.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Audit | `backend/app/agents/audit.py` |
| Observability | `backend/app/services/llm_observability.py` |
## 18.7 关键代码理解
> 轨迹记录模型、Token、耗时和尝试次数，但不保存 API Key、Authorization、完整 Prompt 或原始响应。
## 18.8 最小动手运行
```bash
pytest backend/tests/test_audit_report.py backend/tests/test_llm_observability.py -q
```
## 18.9 故障注入实验
> 触发一个确定性阻断，观察 blocked rules 与事件顺序。
## 18.10 调试路径与常见误判
> 没有成本单价时成本字段应为空，不能伪造为零成本。
## 18.11 独立编码练习
> 设计一个不泄露结果行的执行摘要。
## 18.12 测试或评测验证
> 检查并发调用轨迹是否通过 ContextVar 隔离。
## 18.13 面试复述题
> 可观测性如何帮助区分模型慢、数据库慢和 Repair 多？
## 18.14 掌握度检查与下一章
> 能说明证据与隐私边界。下一部分学习产品 API 与前端。
