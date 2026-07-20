# 第11章 Schema Grounding 与主动澄清
> 本章预计 1～2 小时，学习在生成 SQL 前消除歧义。
## 11.1 学习目标
> 能解释候选、路由表、JOIN 边、置信度和澄清选项。
## 11.2 前置知识
> 需要完成第9～10章。
## 11.3 为什么需要这一模块
> 模糊问题或冲突候选若直接生成 SQL，会把不确定性变成看似确定的查询。
## 11.4 输入、输出与依赖
> 输入是意图、语义和 Schema；输出是 Grounding 或结构化澄清请求。
## 11.5 执行流程
```text
Intent → Candidate Grounding → Route → Confidence → Continue / Clarify
```
## 11.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Grounding | `backend/app/agents/grounding.py` |
| 澄清 | `backend/app/agents/clarification.py` |
## 11.7 关键代码理解
> 关注候选 ID、缺失槽位和冻结原问题；恢复澄清后必须重新经过 Intent Guard。
## 11.8 最小动手运行
```bash
pytest backend/tests/test_schema_grounding_precision.py backend/tests/test_clarification.py -q
```
## 11.9 故障注入实验
> 使用缺少指标的问题观察系统在数据库访问前暂停。
## 11.10 调试路径与常见误判
> 澄清不是失败，也不是让模型自由追问；候选必须稳定并可恢复。
## 11.11 独立编码练习
> 为一个时间范围缺失的问题设计两个不重叠候选。
## 11.12 测试或评测验证
> 检查 Grounding 评测的候选命中和路由召回。
## 11.13 面试复述题
> 为什么主动澄清必须发生在 Schema 加载或 SQL 生成之前？
## 11.14 掌握度检查与下一章
> 能解释继续和暂停条件。下一章进入 LangGraph 编排。
