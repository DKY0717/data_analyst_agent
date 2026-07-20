# 第31章 实战三：从零重建最小 Agent
> 本章预计分两次完成，用一个独立小目录重建可测试的 NL2SQL 核心。
## 31.1 学习目标
> 能不复制现有实现，独立写出 Schema 读取、LLM 结构化生成、SQL 安全校验、执行和答案输出。
## 31.2 前置知识
> 已掌握 Python 异步、FastAPI、数据库、LLM API、SQL Guard 和测试替身。
## 31.3 为什么需要这一模块
> 能看懂代码不等于能独立开发；从空目录重建可以暴露隐藏的知识缺口。
## 31.4 输入、输出与依赖
> 输入是自然语言问题、只读数据库和兼容 LLM；输出是 SQL、列、行和简短解释，依赖最少可替换接口。
## 31.5 执行流程
```text
question → schema → structured LLM output → SQL guard → execute → explain
```
## 31.6 当前代码地图
| 参考边界 | 路径 |
|---|---|
| 配置 | `backend/app/config.py` |
| Schema | `backend/app/db/schema_loader.py` |
| LLM | `backend/app/services/llm_service.py` |
| SQL Guard | `backend/app/security/sql_guard.py` |
| 执行 | `backend/app/db/query_runner.py` |
## 31.7 关键代码理解
> 重建时只参考接口职责，不复制整段实现。先定义可测试协议与失败类型，再接真实数据库和模型，才能保持核心逻辑可离线验证。
## 31.8 最小动手运行
```bash
pytest backend/tests/test_sql_guard.py backend/tests/test_query_runner.py -q
```
## 31.9 故障注入实验
> 用假 LLM 依次返回非法 JSON、写操作 SQL、未知列和合法查询，确认每类错误在正确边界被拦截。
## 31.10 调试路径与常见误判
> 先让假模型路径全绿，再启用真实模型；否则网络、格式、SQL 和数据库错误会同时出现。
## 31.11 独立编码练习
> 在课程外新建个人练习目录，实现五个接口，并为每个接口至少写一个成功和一个失败用例。
## 31.12 测试或评测验证
> 离线测试全部通过后，只用少量非敏感问题做真实模型冒烟；保存结构化证据，不保存密钥。
## 31.13 面试复述题
> 如果不用 LangGraph，你会如何实现一个最小但安全的 NL2SQL Agent？
## 31.14 掌握度检查与下一章
> 能从空目录构建闭环并解释取舍。下一章整理面试演示与项目答辩。
