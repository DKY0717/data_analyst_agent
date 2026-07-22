# 第十七章 NL2SQL 评测体系与质量门禁

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 17.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 区分测试用例、评测用例和真实模型基线；
> 2. 读懂 YAML case 如何描述问题类别和安全预期；
> 3. 理解生成成功、Guard、执行、修复和安全命中率的区别；
> 4. 解释结果正确性、Intent Grounding 和权限评测为什么要分开；
> 5. 读懂 Quality Gate 如何从多个报告计算最终结果；
> 6. 识别评测指标的适用范围，避免用小样本数字夸大系统能力。

## 17.2 问题场景：能跑不等于可靠

> 一次成功查询只能说明一个问题在当前环境下走通。要知道版本升级是否引入回归，需要固定问题集、固定数据、可比较的指标和可追踪的报告。
>
> 项目把评测拆成多个维度：NL2SQL 执行、危险请求阻断、SQL Repair、结果正确性、意图与 Grounding、数据权限和核心路径。不同评测回答不同问题，不能只用一个“准确率”概括全部行为。

## 17.3 Case 文件

> `backend/evaluation/cases/` 使用 YAML 保存固定用例。一个 NL2SQL case 通常包含 ID、自然语言问题、类别和安全预期；核心路径 case 还会链接现有 NL2SQL、黄金结果和权限 case，避免不同评测重复维护同一业务口径。

```yaml
cases:
  - id: monthly_sales_2024
    question: 统计 2024 年每个月的销售额
    category: business_success
    safety_expected: safe
```

> 固定输入让不同代码版本或模型版本可以横向比较。case 文件不是“真实用户世界的全部”，它只是可重复验证的样本边界。

## 17.4 NL2SQL EvaluationRunner

> `EvaluationRunner.evaluate_case()` 对每条问题运行 AgentGraph，然后提取生成 SQL、Guard 结果、执行结果、修复次数、阻断阶段、耗时和 LLM 观测。`evaluate_all()` 按顺序运行全部 case，并在 case 之间等待，避免触发服务端限流。

| 指标 | 回答的问题 |
|---|---|
| `generation_success_rate` | 是否产生了可用 SQL 文本 |
| `guard_pass_rate` | SQL 是否通过安全校验 |
| `execution_success_rate` | 数据库是否执行成功 |
| `safe_execution_success_rate` | 安全 case 是否执行成功 |
| `unsafe_block_rate` | 危险 case 是否按预期阻断 |
| `repair_success_rate` | 发生修复后是否最终成功 |
| `average_retry_count` | 每题平均修复次数 |
| `average_llm_total_tokens` | 模型调用成本观察 |

> 例如，危险问题被阻断时，`execution_success_rate` 可能为 0，但 `unsafe_block_rate` 应该为 1。把所有“未执行”都当成失败，会错误评价安全行为。

## 17.5 安全预期与阻断阶段

> 评测会区分 `intent_guard` 和 `sql_guard` 阻断阶段。高置信危险意图应在模型调用和数据库访问前被 Intent Guard 拦截；模型生成的危险 SQL 则应该在 SQL Guard 阶段被阻断。这个阶段信息可以帮助判断安全层是否提前工作。

```text
safety_expected: safe
  → 期望执行成功

safety_expected: unsafe
  → 期望 intent_guard 或 sql_guard 阻断
```

## 17.6 结果正确性黄金基准

> `golden_result_cases.yaml` 保存预期的列、行或聚合结果，用于验证 SQL 虽然执行成功，但数值和口径是否正确。执行成功率高不代表结果正确；一个错误 JOIN 也可能返回合法的表格。

> 黄金基准应该注明比较方式、排序和允许误差。金额、日期和浮点结果不能简单依赖字符串完全相等；当前项目的比较器和报告写入器负责把差异转换成稳定指标。

## 17.7 Intent Grounding 评测

> `intent_grounding_cases.yaml` 检查指标、维度、缺失槽位、候选命中、路由表召回、澄清决策和澄清候选等中间结果。它不只看最终 SQL，因为最终错误可能来自意图理解、Grounding 或 SQL 生成不同阶段。

| 阶段 | 示例指标 |
|---|---|
| 意图 | `slot_match_rate` |
| 候选 | `grounding_candidate_hit_rate` |
| 路由 | `route_table_recall_rate` |
| 澄清决策 | `clarification_decision_accuracy` |
| 澄清候选 | `clarification_option_hit_rate` |

## 17.8 数据权限评测

> 权限评测不需要真实 LLM 或真实外部数据库，可以给定 SQL、角色和策略，检查允许/阻断决策、命中规则、行过滤预期和授权 SQL 是否发生改写。它是安全回归的重要确定性证据。

> 权限评测应该覆盖允许和拒绝两类样本，例如 analyst 的订单销售额、analyst 的客户姓名、support 的支付字段和 admin 的全字段访问。只测“拒绝成功”会漏掉合法查询被误杀的问题。

## 17.9 Quality Gate

> `backend/evaluation/quality_gate.py` 从 NL2SQL、Repair、正确性、Intent Grounding 和权限报告读取指标，并与固定阈值比较。当前门禁把主要质量指标设为 1.0，任何必要指标缺失或低于阈值都会使 enforce 模式返回非零退出码。

```python
checks.append({
    "metric": metric,
    "actual": actual,
    "threshold": threshold,
    "passed": actual >= threshold,
})
```

> 门禁不是让数字“看起来好看”，而是把交付标准写成机器可检查的条件。阈值必须结合 case 数量、失败样本和真实模型运行条件解释；小样本 100% 不等于任意问题 100% 正确。

## 17.10 报告和证据链

```text
固定 cases
  ↓
EvaluationRunner / 专项 evaluator
  ↓
JSON + Markdown 报告
  ↓
Quality Gate
  ↓
Security Audit / CI artifact
```

> JSON 适合机器读取和下一次比较，Markdown 适合人阅读和面试展示。真实模型报告还应记录 provider、model、代码 HEAD、运行模式和报告生成时间，避免把旧模型的结果误归因于当前代码。

## 17.11 可执行核心路径

> 结构化评测主要验证单一指标或模块；`backend/evaluation/core_path_runner.py` 额外验证一条完整的用户路径。它只把外部 LLM 替换成确定性 Fake LLM，仍然运行真实 AgentGraph、Grounding、Intent/SQL Guard、权限改写、优化器、隔离 DuckDB 和 SQLite 多轮会话。当前核心路径包有 15 条场景，结果包含状态、阻断规则、缺失 surface 和表面完整率。

```bash
cd backend
python -m evaluation.core_path_runner
```

> 看到 `llm_mode=deterministic_fixture` 不代表“只测了假流程”；应同时检查报告中的 `agent_graph=real`、`database_mode=isolated_duckdb_copy` 和 `surface_completeness_rate`。这类证据适合本地回归和面试演示，不替代真实模型质量报告。

## 17.12 代码地图

| 文件或目录 | 作用 | 阅读重点 |
|---|---|---|
| `backend/evaluation/evaluator.py` | NL2SQL 批量评测 | case 执行和指标汇总 |
| `backend/evaluation/cases/` | 固定评测输入 | 业务、安全、修复和黄金结果 |
| `backend/evaluation/quality_gate.py` | 质量门禁 | 指标来源、阈值和退出码 |
| `backend/evaluation/core_path_runner.py` | 核心路径回归 | Fake LLM 边界与真实 Agent 执行 |
| `backend/evaluation/result_correctness_evaluator.py` | 结果正确性 | 预期与实际比较 |
| `backend/evaluation/intent_grounding_evaluator.py` | 意图与路由 | 槽位、候选和路径 |
| `backend/evaluation/permission_evaluator.py` | 权限回归 | 角色、规则和 SQL 改写 |
| `backend/tests/test_evaluator.py` | 评测运行器测试 | 汇总和边界 |
| `backend/tests/test_quality_gate.py` | 门禁测试 | 缺字段、阈值和退出码 |
| `backend/tests/test_core_path_cases.py` | 核心路径资产契约 | 场景、surface 和关联 case |

## 17.13 动手验证

> 先运行确定性评测相关测试：

```bash
pytest backend/tests/test_evaluator.py backend/tests/test_quality_gate.py backend/tests/test_core_path_cases.py -q
```

> 若已初始化 DuckDB，再运行完整核心路径：

```bash
cd backend
python -m evaluation.core_path_runner
```

> 可以运行离线权限评测，不调用 LLM：

```bash
cd backend
python -m evaluation.permission_evaluator --json
```

> 真实模型评测需要有效 API Key、可访问端点和费用预算。运行后应保存 JSON/Markdown 报告，并核对模型、代码 HEAD 和 case pack 版本。

## 17.14 常见错误

### 把生成成功当成结果正确

> 有 SQL 文本不代表 SQL 可执行，更不代表指标口径正确。至少分开观察生成、Guard、执行和黄金结果。

### 把危险请求阻断算作失败

> 对安全预期为 unsafe 的 case，阻断才是成功。应查看 `safety_expectation_met` 和 `blocked_stage`。

### 缺少报告输入却显示为 0 分

> Quality Gate 应把缺失必要指标视为输入错误或未验证，而不是伪造 0 或默认通过。报告中要区分“未提供真实输入”和“真实评测失败”。

### 用单次真实模型结果证明稳定性

> 模型、网络、Prompt 和数据都可能变化。需要固定 case、多次运行、保存元数据并结合确定性回归。

## 17.15 本章小结

> 评测把“系统看起来能用”转成可复核的行为证据：NL2SQL 看执行，黄金基准看结果，Intent Grounding 看中间理解，权限评测看授权边界，Quality Gate 把要求写成机器条件。指标必须和样本、模型和运行模式一起解释。

## 17.16 练习

1. 为一个安全 case 写出它的 `safety_expected` 和正确阻断阶段。
2. 解释为什么同一个问题可以同时出现在 NL2SQL 和黄金结果 case 中。
3. 构造一份缺少 `result_correctness_rate` 的报告，观察 Quality Gate 的处理。
4. 对比 `execution_success_rate` 和 `result_correctness_rate` 的分母和含义。
5. 说明为什么权限评测可以在不调用 LLM 的情况下证明部分安全行为。

## 17.17 下一章衔接

> 测试和评测已经能回答“当前代码是否满足预期”，但还需要把后端、前端和代理配置打包成可交付环境。下一章会学习 Docker、Nginx、Compose 和 GitHub Actions。
