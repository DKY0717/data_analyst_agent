# 第8章 最小 NL2SQL 流水线

> 本章预计 1～2 小时，把前3章组成最小闭环，再明确为什么生产链路必须继续演进。默认只使用 Fake LLM 与隔离 DuckDB。

## 8.1 学习目标
> 能串起问题、Schema、结构化 SQL 生成、执行结果和答案；定义每一步接口与失败；指出最小链路至少六个生产风险。

## 8.2 前置知识
> 需要完成第5～7章，理解 Schema Loader、FastAPI 和 LLM 客户端。

## 8.3 为什么需要这一模块
> 完整 Agent 模块很多。先建立最小闭环可以看清核心价值，再理解后续安全、权限和修复为何逐层加入。

## 8.4 输入、输出与依赖
| 阶段 | 输入 | 输出 |
|---|---|---|
| Schema | 数据库连接 | 物理 Schema 字典 |
| SQL Generator | 问题、Schema、可选上下文 | `SQLGeneratorOutput` |
| Query Runner | SQL 字符串 | success、columns、rows、耗时/错误 |
| Answer Generator | 问题、SQL、结构化结果 | 答案文本 |

## 8.5 执行流程
```text
Question → SchemaLoader
Question + Schema → SQLGenerator(Fake/LLM)
SQL → [生产必须有 Guard/Permission] → QueryRunner
Question + SQL + Result → AnswerGenerator
```

## 8.6 当前代码地图
| 模块 | 路径 |
|---|---|
| SQL 生成 | `backend/app/agents/sql_generator.py` |
| Schema | `backend/app/db/schema_loader.py` |
| SQL 执行 | `backend/app/db/query_runner.py` |
| 答案 | `backend/app/agents/answer_generator.py` |
| 结构模型 | `backend/app/models/schemas.py` |

## 8.7 关键代码理解
### 8.7.1 SQLGenerator 的职责

> 它把物理 Schema、语义摘要、结构化 Intent 和多轮摘要格式化后调用统一客户端；再用 `SQLGeneratorOutput` 固定 `sql/tables/columns/explanation`。列名从 SQLGlot AST 提取，比相信模型自报更可靠，但这一步本身不是安全 Guard。

### 8.7.2 QueryRunner 的职责

> 执行器选择 sandbox 或 direct，返回结构化成功/失败。它不会证明业务语义，也不应承担自然语言理解。生产中 SQL 必须先经过 Guard 与权限。

### 8.7.3 AnswerGenerator 的职责

> 它只把已执行结果解释为自然语言。如果答案生成失败，已成功 SQL 与行结果仍是有效结构化证据，不应被清空或重新执行数据库。

### 8.7.4 最小链路的风险清单

| 缺失能力 | 风险 |
|---|---|
| Intent Guard | 危险请求进入模型/数据库链路 |
| Clarification | 歧义被模型擅自猜测 |
| SQL AST Guard | DDL/DML、危险函数、系统对象 |
| Permission | 越表、越列、越行读取 |
| LIMIT/timeout/sandbox | 资源耗尽 |
| Repair/错误分类 | 暂态与确定性错误混在一起 |
| Audit/trace | 无法证明执行了什么 |
| 结果正确性评测 | 可执行 SQL 被误认为正确 |

## 8.8 最小动手运行
```bash
pytest backend/tests/test_sql_generator.py backend/tests/test_query_runner.py -q
```
> 工作目录：项目根目录。网络/真实模型：不需要；测试注入 Fake LLM 和隔离连接。

## 8.9 故障注入实验
> 让 Fake LLM 返回 `SELECT missing_column FROM orders`。预期生成阶段成功、执行阶段结构化失败；再返回合法只读 SQL 恢复。实验只连接临时 DuckDB。

## 8.10 调试路径与常见误判
> 按中间产物调试：Schema 是否含目标列；Fake/LLM 是否返回合约；SQL 是否能解析；Guard/权限是否通过；执行器返回什么；答案是否忠于 rows。生成 SQL、执行成功和答案流畅分别都不是正确性证明。

## 8.11 独立编码练习
> 用依赖注入写 `run_mini_query(question, loader, generator, runner, answerer)`，返回 SQL、columns、rows、answer 与 error_type。不得使用全局真实客户端，不得捕获所有异常后只返回空字符串。

## 8.12 测试或评测验证
> 至少写四例：合法查询；模型缺字段；未知列执行失败；答案生成失败但保留 SQL/rows。然后运行：

```bash
pytest backend/tests/test_sql_generator.py backend/tests/test_query_runner.py backend/tests/test_answer_generator.py -q
```

## 8.13 面试复述题
> 1. 最小 NL2SQL 为什么不能直接连接企业数据库？
>
> 2. SQLGenerator 从 AST 提列为什么仍不等于 SQL Guard？
>
> 3. 答案生成失败后，哪些结果必须保留？

## 8.14 掌握度检查与下一章
> 能不用框架伪代码描述四个接口；能用 Fake LLM 测成功与失败；能指出至少六个风险。下一章加入结构化分析意图。
