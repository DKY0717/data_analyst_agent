# 第14章 Intent Guard 与 SQL Guard
> 本章预计 2 小时，学习两层确定性安全边界。
## 14.1 学习目标
> 能区分危险自然语言和危险 SQL AST。
## 14.2 前置知识
> 需要理解 SQL 和 Agent 路由。
## 14.3 为什么需要这一模块
> LLM 不能自行保证安全，危险请求应尽早阻断，所有生成 SQL 仍需独立验证。
## 14.4 输入、输出与依赖
> Intent Guard 输入问题；SQL Guard 输入 SQL；输出允许、阻断规则和规范化 SQL。
## 14.5 执行流程
```text
Question → Intent Guard → LLM → SQL → SQLGlot AST Guard
```
## 14.6 当前代码地图
| 内容 | 路径 |
|---|---|
| Intent | `backend/app/security/intent_guard.py` |
| SQL | `backend/app/security/sql_guard.py` |
## 14.7 关键代码理解
> SQL Guard 只允许 SELECT/WITH，拦截系统表、文件函数和危险函数，并处理 LIMIT；解析失败时 fail closed。
## 14.8 最小动手运行
```bash
pytest backend/tests/test_intent_guard.py backend/tests/test_sql_guard.py -q
```
## 14.9 故障注入实验
> 比较“删除订单表”和模型生成 `DROP TABLE` 的阻断阶段。
## 14.10 调试路径与常见误判
> 字符串关键词不能代替 AST；安全阻断是预期成功，不应计作普通执行失败。
## 14.11 独立编码练习
> 为一个新的危险 DuckDB 文件函数设计测试预期，不直接修改生产规则。
## 14.12 测试或评测验证
> 检查空 SQL、WITH、EXPLAIN、系统表和 LIMIT 边界测试。
## 14.13 面试复述题
> 为什么有 Intent Guard 仍然必须保留 SQL Guard？
## 14.14 掌握度检查与下一章
> 能解释两层输入和规则。下一章学习执行沙箱与资源限制。
