# 第8章 最小 NL2SQL 流水线

> 本章预计 1～2 小时，先理解最小闭环，再明确它的安全缺口。

## 8.1 学习目标
> 能串起问题、Schema、Prompt、SQL、执行结果和自然语言答案。

## 8.2 前置知识
> 需要完成第5～7章，理解 Schema Loader、FastAPI 和 LLM 客户端。

## 8.3 为什么需要这一模块
> 完整 Agent 模块很多。先建立最小闭环可以看清核心价值，再理解后续安全、权限和修复为何逐层加入。

## 8.4 输入、输出与依赖
> 输入是问题和 Schema；中间产物是 SQL 与结果行；输出是答案；依赖 SQL Generator、QueryRunner 和 Answer Generator。

## 8.5 执行流程
```text
Question + Schema → SQL Generator → QueryRunner → Answer Generator
```

## 8.6 当前代码地图
| 模块 | 路径 |
|---|---|
| SQL 生成 | `backend/app/agents/sql_generator.py` |
| SQL 执行 | `backend/app/db/query_runner.py` |
| 答案 | `backend/app/agents/answer_generator.py` |

## 8.7 关键代码理解
> 观察各模块之间传递的是结构化对象而不是任意字符串。当前生产链路还会加入 Guard、权限和状态管理，本章只抽取最小因果链。

## 8.8 最小动手运行
```bash
pytest backend/tests/test_sql_generator.py backend/tests/test_query_runner.py -q
```

## 8.9 故障注入实验
> 让 Fake LLM 返回不存在的列，观察生成成功但执行失败的差别；不要连接真实生产数据库。

## 8.10 调试路径与常见误判
> 生成了 SQL 不等于通过安全校验，执行成功也不等于业务口径正确，答案自然流畅更不能证明底层数据正确。

## 8.11 独立编码练习
> 用 Fake LLM 和隔离 DuckDB 写一个最小练习函数，返回 SQL、列名、行数和错误类型。

## 8.12 测试或评测验证
> 为安全结果、执行错误和答案生成错误分别写出预期，不使用真实模型。

## 8.13 面试复述题
> 最小 NL2SQL 为什么只能用于学习，不能直接连接企业数据库？

## 8.14 掌握度检查与下一章
> 能画出最小闭环并指出至少四个风险。下一章开始加入结构化分析意图。
