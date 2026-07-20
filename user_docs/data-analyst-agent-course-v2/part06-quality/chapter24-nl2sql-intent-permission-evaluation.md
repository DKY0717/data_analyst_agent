# 第24章 NL2SQL、意图与权限评测
> 本章预计 1～2 小时，学习如何把“感觉能用”变成可计算指标。
## 24.1 学习目标
> 能区分 SQL 生成、意图理解、语义落地和权限执行的评测目标。
## 24.2 前置知识
> 熟悉 Intent、Grounding、SQL Guard 与权限改写。
## 24.3 为什么需要这一模块
> 一条最终 SQL 错误可能来自多个阶段；分层评测才能定位是理解、映射、生成还是权限问题。
## 24.4 输入、输出与依赖
> 输入是版本化 YAML 用例与当前实现；输出是逐例结果、汇总指标和失败原因。
## 24.5 执行流程
```text
cases → runner/evaluator → per-case evidence → report → thresholds
```
## 24.6 当前代码地图
| 内容 | 路径 |
|---|---|
| NL2SQL | `backend/evaluation/evaluator.py` |
| 意图 | `backend/evaluation/intent_evaluator.py` |
| Grounding | `backend/evaluation/intent_grounding_evaluator.py` |
| 权限 | `backend/evaluation/permission_evaluator.py` |
| 用例 | `backend/evaluation/cases/` |
## 24.7 关键代码理解
> 每类评测拥有独立通过条件。执行成功不等于语义正确，权限策略声明正确也不等于最终 SQL 真正受限。
## 24.8 最小动手运行
```bash
pytest backend/tests/test_evaluator.py backend/tests/test_intent_evaluator.py backend/tests/test_permission_evaluator.py -q
```
## 24.9 故障注入实验
> 将一个业务指标映射到错误列，观察 Grounding 指标与最终 SQL 指标如何分别暴露问题。
## 24.10 调试路径与常见误判
> 先读逐例 reason 和证据，再看聚合分数；总分下降不能直接告诉你哪个节点失效。
## 24.11 独立编码练习
> 增加一条“退款金额按地区汇总”的评测用例，并写清期望语义与失败条件。
## 24.12 测试或评测验证
> 先运行评测组件单测，再在明确启用真实模型的环境运行对应评测入口。
## 24.13 面试复述题
> 为什么本项目要把 Intent Grounding 和 NL2SQL 分开评分？
## 24.14 掌握度检查与下一章
> 能根据失败证据定位到具体层。下一章评测 Repair 和结果正确性。
