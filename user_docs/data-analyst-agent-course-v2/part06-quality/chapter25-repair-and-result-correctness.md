# 第25章 SQL Repair 与结果正确性评测

> 本章预计 1～2 小时。你将建立一条非常重要的质量边界：SQL 可解析、可执行、经过修复，都不等于业务结果正确。

## 25.1 学习目标

> 完成本章后，你应该能够：
>
> - 解释为什么 Repair 需要独立、可重复的故障注入；
> - 区分修复输出、Guard 通过、执行成功、意图保持和端到端修复成功；
> - 说明黄金参考 SQL 的作用与局限；
> - 解释列契约、行数、集合、顺序、浮点容差和固定断言；
> - 设计一个“SQL 能执行但答案错误”的评测用例。

## 25.2 前置知识

> 你已经理解 SQL Repair 节点的重试流程、SQL Guard 和 QueryRunner，也知道上一章中的“执行成功”只是一项阶段证据。

## 25.3 为什么需要这一模块

> `SELECT COUNT(*) FROM orders` 和 `SELECT SUM(total_amount) FROM orders` 都可能成功执行，但它们回答的是不同问题。错误 JOIN 还可能造成重复聚合，错误过滤可能漏掉年份，错误排序会让 Top N 结果完全失真。数据库不报错，只说明 SQL 在语法与运行层面可接受。
>
> Repair 也有同样问题。模型把不存在的列改成任意存在列，SQL 就能运行，却可能改变原问题。因此本项目把 Repair 能力和最终结果正确性做成两套评测：前者证明可控故障能否被安全修复且保留意图，后者把 Agent 结果与黄金参考结果进行确定性比较。

## 25.4 输入、输出与依赖

| 套件 | 主要输入 | 主要输出 | 当前默认 case 数 |
|---|---|---|---|
| Repair | 确定会失败的 SQL、期望表、必需/禁止片段 | 故障注入、修复、Guard、执行、意图保持 | 6 |
| Result Correctness | 问题、黄金 SQL、比较模式、固定断言 | 列/值/顺序/断言与最终正确性 | 10 |

> Repair 评测依赖当前 LLM RepairAgent、SchemaLoader、SQL Guard 和 QueryRunner。结果正确性评测依赖 Agent、ReferenceQueryRunner 和 ResultComparator。两者都支持单 case 失败隔离，避免一个异常吞掉整份报告。

## 25.5 执行流程

### Repair 评测

```text
预置错误 SQL
  → SQL Guard 允许进入只读执行
  → 原 SQL 必须执行失败
  → 调用 RepairAgent
  → 修复 SQL 再过 SQL Guard
  → 再执行
  → 检查表与必需/禁止 SQL 片段
  → 全部成立才算端到端 Repair 成功
```

### 结果正确性评测

```text
自然语言问题 → Agent SQL 与结果
黄金 SQL → ReferenceQueryRunner → 参考结果
两份结构化结果 → ResultComparator
  → 列契约
  → 行数与值集合
  → 必要时检查顺序
  → 固定业务断言
  → result_correct
```

> 两条流程刻意独立。固定错误 SQL 让 Repair 能力不受上游 SQL Generator 是否“碰巧生成正确 SQL”干扰；黄金结果比较则直接验证业务答案，不把 Repair 次数当成准确率替代品。

## 25.6 当前代码地图

| 内容 | 路径 | 阅读重点 |
|---|---|---|
| Repair 评测 | `backend/evaluation/repair_evaluator.py` | 故障注入与五段成功条件 |
| Repair cases | `backend/evaluation/cases/sql_repair_cases.yaml` | 可重复错误与意图片段 |
| 参考查询执行 | `backend/evaluation/reference_query_runner.py` | 黄金 SQL 也先过 Guard |
| 结果比较器 | `backend/evaluation/result_comparator.py` | 四种模式与容差 |
| 正确性评测 | `backend/evaluation/result_correctness_evaluator.py` | Agent/参考结果编排 |
| 黄金 cases | `backend/evaluation/cases/golden_result_cases.yaml` | reference_sql 与 fixed_assertions |
| Repair 测试 | `backend/tests/test_repair_evaluator.py` | 原 SQL 意外成功时不得算注入成功 |
| 正确性测试 | `backend/tests/test_result_correctness_evaluator.py` | 失败类型和汇总口径 |

## 25.7 关键代码理解

### Repair：先证明故障真的存在

> `RepairEvaluationRunner.evaluate_case()` 先让原 SQL 经过 Guard。若原 SQL 本身危险，流程停止，因为这不是“可修复的只读 SQL 错误”；若原 SQL意外执行成功，也停止并标记未形成确定性故障注入。只有 Guard 允许且数据库明确执行失败，`failure_injected` 才为真。
>
> 修复后还要重新通过 Guard 和执行器，并用固定片段检查意图。例如错误字段 `revenue` 修成 `total_amount` 时，期望表必须仍包含 `orders`，必需片段必须出现，禁止片段必须消失。

```text
end_to_end_success =
  failure_injected
  AND repair_output_success
  AND repaired_guard_passed
  AND execution_success
  AND intent_preserved
```

> 摘要为这五个阶段分别计算比例，分母固定为 Repair case 总数。若原错误 SQL 因数据库变化突然可执行，`failure_injection_rate` 会下降，不能把该 case 当成 Repair 成功。

### 黄金参考 SQL：是可审查的 oracle，不是天然真理

> `ReferenceQueryRunner` 会先用 SQL Guard 校验黄金 SQL，再执行它。黄金 SQL 被 Guard 拦截或执行失败时，case 的失败类型分别是 `reference_guard_blocked` 或 `reference_execution_failed`，不会把坏黄金答案拿去比较。
>
> 黄金 SQL 仍需要人工审查其指标口径、表粒度和 JOIN 关系。它的优势是版本化、可重复和可执行，不代表作者绝不会写错，所以本项目还允许用 `fixed_assertions` 锁定已知行数、列求和或标量值。

### ResultComparator：比较结构化结果，不比较 SQL 字符串

> 同一业务问题可能有多种等价 SQL，因此直接比较 SQL 文本会误报。比较器读取 `columns` 与 `rows`，按 case 指定的 `required_columns` 锁定完整列契约：候选结果多列或少列都失败。
>
> 当前支持四种模式：`unordered` 忽略行顺序，`ordered` 要求完整顺序，`top_n` 要求 Top N 顺序，`scalar` 用于单值指标。ordered/top_n 必须提供合法 `order_by`，unordered/scalar 则不接受该配置。
>
> 数值比较使用绝对容差，默认 `0.001`。这用于处理浮点/Decimal 表达差异，但容差不是越大越好；过大会掩盖真实业务误差。非数值、空值和日期等仍按确定性规则比较。
>
> 固定断言作用于黄金结果，可检查 `row_count`、某列求和或单个标量。比较器最多返回有限差异样本，既便于调试，也避免把完整业务结果塞进评测报告。

### 正确性指标的含义

> `result_correctness_rate` 要求比较器的全部条件通过。`column_match_rate`、`value_match_rate`、`order_match_rate` 用于定位失败阶段；`business_metric_accuracy` 只以 `category: business_metric` 的子集为分母。参考 Guard、参考执行和固定断言也各有独立比例。
>
> 这里仍需留意语义：对于 unordered/scalar 模式，不需要业务顺序，因此 `order_matched` 会按该模式契约处理。引用顺序准确率时必须连同 case 模式分布一起解释，不能把它误说成所有查询都验证了排序。

## 25.8 最小动手运行

> 先运行两套评测器的测试。这些测试使用固定替身验证流程与指标，不会调用真实 MiMo。

```powershell
pytest backend/tests/test_repair_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
```

> 然后只读查看两个 case pack，任选一条 Repair 和一条黄金结果 case，手写它们的通过条件。

```powershell
Get-Content backend/evaluation/cases/sql_repair_cases.yaml -TotalCount 80
Get-Content backend/evaluation/cases/golden_result_cases.yaml -TotalCount 100
```

> 不建议直接运行 Repair 或 correctness 的真实入口，除非你明确配置了外部模型、数据库快照和报告目录。测试通过证明评测框架契约，不证明真实模型已通过全部 case。

## 25.9 故障注入实验

> 设计一个“可执行但错误”的候选结果：把销售额问题的 `SUM(total_amount)` 换成 `COUNT(*)`。两条 SQL 都可能通过 Guard 并成功执行，但结果比较应因列名、值或固定断言失败。

```sql
-- 正确口径示意
SELECT SUM(total_amount) AS sales_amount FROM orders;

-- 可执行但业务错误
SELECT COUNT(*) AS sales_amount FROM orders;
```

> 再做一个顺序实验：保持 Top 5 的五行和值完全相同，只反转行顺序。unordered 模式可以通过集合比较，但 top_n 模式必须产生 `order_mismatch`。这说明“值相同”不总等于“答案相同”。
>
> 最后把一个 Repair case 的错误字段改成数据库中真实存在的字段。原 SQL可能意外执行成功，此时正确行为是 `failure_injected: false` 并跳过 Repair，而不是假装模型完成了一次修复。

## 25.10 调试路径与常见误判

> Repair 失败建议按以下顺序查：原 SQL 是否通过 Guard、是否真的失败、Repair 是否返回结构化输出、修复 SQL 是否再次通过 Guard、是否执行成功、意图片段是否满足。不要只看最后一个 `end_to_end_success`。
>
> 正确性失败先看 `failure_type` 与 `comparison_failure_types`：参考侧失败先修黄金 case；`column_mismatch` 查输出契约；`row_count_mismatch` 查过滤/JOIN/聚合；`value_mismatch` 查口径和数据；`order_mismatch` 查 ORDER BY 与 Top N；`fixed_assertion_failed` 查黄金口径或固定数据。
>
> 常见误判一：Repair 执行成功率就是 Repair 成功率。它没有包含确定性故障、Guard 和意图保持条件。
>
> 常见误判二：SQL 文本不同就是错误。等价改写应该用结果比较判断，而不是字符串相等。
>
> 常见误判三：容差可以随意调大让测试通过。容差是业务契约的一部分，应依据金额精度、比例尺度等明确设置。
>
> 常见误判四：黄金 SQL 一定正确。它必须通过 Guard、可执行，并接受业务口径审查与固定断言校验。

## 25.11 独立编码练习

> 为“2024 年平均客单价”设计一条完整黄金 case 草案。写出问题、reference SQL、`scalar` 比较模式、完整输出列和合理绝对容差；如果使用固定标量断言，说明该值依赖哪个数据库快照。

```yaml
# 练习骨架，不是现有 case 的复制
id: <case_id>
question: <问题>
category: business_metric
reference_sql: |
  SELECT <业务公式> AS <稳定别名>
  FROM <表>
  WHERE <固定范围>
comparison:
  mode: scalar
  required_columns: [<稳定别名>]
  absolute_tolerance: <经过解释的值>
fixed_assertions:
  scalar:
    column: <稳定别名>
    value: <固定快照下的已知值>
```

> 自查三个陷阱：分子分母是否正确、是否因 JOIN 重复计数、是否漏掉时间过滤。练习目标是建立业务 oracle，不是追求 SQL 写得短。

## 25.12 测试或评测验证

> 本章专项验证命令覆盖 Repair 的完整分段契约、单 case 异常隔离、分片入口，以及 correctness 的参考失败、比较失败、汇总分母和空集合行为。

```powershell
pytest backend/tests/test_repair_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
```

> 额外运行比较器测试，可以更细地观察 unordered、ordered、top_n、scalar、容差和差异样本。

```powershell
pytest backend/tests/test_result_comparator.py backend/tests/test_reference_query_runner.py -q
```

> 验收结论必须写成“评测框架与固定替身测试通过”，不能写成“真实模型结果正确率通过”。真实证据还必须满足第 26～28 章的完整分片和严格汇总要求。

## 25.13 面试复述题

> **问题：一条 SQL 成功执行后，还需要哪些证据才能说答案正确？**
>
> 合格回答：需要可信的业务 oracle；本项目执行经 Guard 校验的黄金 SQL，再比较完整列契约、行数、值集合、必要的排序和固定业务断言，并对浮点使用明确容差。还要确认数据快照、case 数和代码版本一致。
>
> **追问：怎么独立证明 Repair 能力？**
>
> 应回答：使用固定、可重复、Guard 允许但数据库必然失败的 SQL 注入故障；修复后重新过 Guard 和执行器，再用预期表及必需/禁止片段检查意图保持。不能依赖 SQL Generator 偶然出错来触发 Repair。

## 25.14 掌握度检查与下一章

> 如果你能解释“可执行、已修复、意图保持、结果正确”四者的差异，并能为错误 JOIN、错误聚合、错误排序分别选择断言，就算掌握本章。
>
> 下一章处理工程现实：真实模型评测很长、会超时、会部分成功。我们要让分片可恢复，同时阻止不完整证据被汇总成一个看似成功的结论。
