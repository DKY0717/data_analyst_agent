# 第24章 NL2SQL、意图与权限评测

> 本章预计 1～2 小时。目标是把“这个 Agent 感觉还行”拆成可以定位、复查和比较的指标，并学会识别错误分母造成的漂亮假象。

## 24.1 学习目标

> 完成本章后，你应该能够：
>
> - 区分 SQL 生成、SQL 安全、查询执行、Intent、Grounding、澄清和权限评测；
> - 解释每个比例的分子和分母；
> - 说明危险请求被阻断为什么是成功，而不是执行失败；
> - 阅读逐例 reason、阶段、规则 ID 和汇总指标来定位故障层；
> - 在引用评测结果时同时给出 case 数、provider/model 和代码 HEAD。

## 24.2 前置知识

> 你已经理解 Intent、Grounding、Clarification、SQL Guard 和数据权限节点。本章不重新讲节点实现，而是学习如何分别证明它们达成契约。

## 24.3 为什么需要这一模块

> 一条最终 SQL 错误可能来自很多位置：用户意图解析错了、业务概念映射错了、JOIN 路由错了、模型生成错了、SQL 被安全规则拒绝、数据库执行失败，或者权限改写改变了结果。如果只看“最终成功率”，这些故障会混在一起。
>
> 更危险的是分母错误。把危险请求的“没有执行”计为普通执行失败，会低估系统；把权限拒绝当成危险 SQL 已成功阻断，又会高估安全性。分层评测的价值就是让每类成功有自己的定义。

## 24.4 输入、输出与依赖

| 评测套件 | 输入 | 是否调用 LLM/DB | 主要输出 |
|---|---|---|---|
| NL2SQL | `ecommerce_nl2sql_cases.yaml` 的问题与安全期望 | 默认走 Agent | 生成、Guard、执行、阻断、Repair、LLM 开销 |
| Intent/Grounding | `intent_grounding_cases.yaml` 的结构化期望 | 否 | slot、候选、路由、JOIN、澄清指标 |
| Permission | 6 个固定角色/SQL 场景 | 不调用 LLM；调用权限 Guard | 决策、规则、行过滤、SQL 改写准确率 |

> NL2SQL 默认 case pack 当前有 65 条；Intent/Grounding 文件当前至少有 7 条；权限评测默认固定 6 条。数量是当前源码事实，不是永远不变的产品承诺，引用报告时仍要读取报告中的 `total_cases`。

## 24.5 执行流程

```text
版本化 case
  → 运行对应 evaluator
  → 每条 case 生成稳定证据
  → 单条异常转为失败并继续
  → 按明确分母聚合 summary
  → 报告与 provider/model/HEAD 绑定
  → 质量门禁判断是否达标
```

> 确定性的 Intent/Grounding 与 Permission 可以在普通 CI 中频繁运行。真实 NL2SQL 会受 API、模型和网络影响，因此还需要第 26～28 章的分片、checkpoint 和证据完整性检查。

## 24.6 当前代码地图

| 内容 | 路径 | 阅读重点 |
|---|---|---|
| NL2SQL 评测器 | `backend/evaluation/evaluator.py` | 阶段字段与安全分母 |
| Intent/Grounding 评测器 | `backend/evaluation/intent_grounding_evaluator.py` | 无 LLM/DB 的确定性链路 |
| 权限评测器 | `backend/evaluation/permission_evaluator.py` | 角色、规则、行过滤、fail-closed |
| NL2SQL cases | `backend/evaluation/cases/ecommerce_nl2sql_cases.yaml` | 问题、类别与 safety_expected |
| Intent/Grounding cases | `backend/evaluation/cases/intent_grounding_cases.yaml` | slot 与路由期望 |
| NL2SQL 测试 | `backend/tests/test_evaluator.py` | 阻断阶段和分母约束 |
| Intent/Grounding 测试 | `backend/tests/test_intent_grounding_evaluator.py` | 各层指标契约 |
| 权限测试 | `backend/tests/test_permission_evaluator.py` | 六个默认场景必须通过 |

## 24.7 关键代码理解

### NL2SQL：先给 case 分类，再讨论成功

> `EvaluationRunner.evaluate_case()` 从 Agent 最终 state 提取生成 SQL、验证 SQL、执行状态、重试次数和 LLM 观测数据。它还计算 `blocked_stage`：可能是 `intent_guard`、`sql_guard`、`permission_guard`、`agent_error` 或 `none`。
>
> 对 `safety_expected: safe` 的 case，安全期望达成意味着成功执行；对 `safety_expected: unsafe` 的 case，必须由 Intent Guard 或 SQL Guard 阻断才算达成。权限拒绝不能冒充危险意图/SQL 阻断，因为二者回答的问题不同。

```text
安全 case：execution_success == true 才算安全期望达成
危险 case：blocked_stage ∈ {intent_guard, sql_guard} 才算安全期望达成
权限拒绝：属于 permission_guard，不替代危险请求安全阻断
```

> 摘要同时给出所有 case 的 `execution_success_rate`、只看安全 case 的 `safe_execution_success_rate`、只看危险 case 的 `unsafe_block_rate`，以及 Intent Guard 与 SQL Guard 各自的阻断比例。面试时应优先引用后两类分层指标，而不是拿一个混合总数模糊表述。

### Intent/Grounding：把理解和物理路由拆开

> `IntentGroundingEvaluationRunner` 直接运行规则解析器、Grounder 和 Clarification，不调用 LLM，也不访问数据库。它检查 metric、dimension、filter、ranking 是否匹配，再检查语义候选、路由表集合、JOIN 边和澄清选项。
>
> `slot_match_rate` 的分子是一条 case 的四类 slot 检查全部通过，分母是全部 Intent/Grounding cases。`route_table_recall_rate` 和 `route_table_precision` 则先对每条 case 计算，再取平均。一个是“该走的表有没有漏”，另一个是“选中的表有没有多余”。
>
> `all_expectations_met_rate` 要求该 case 的所有检查同时成立；只有结果非空且该比例等于 1.0，摘要中的 `passed` 才为真。这个严格结论适合作为确定性回归门禁。

### Permission：不仅看 allow/deny

> 权限评测的 6 个默认场景覆盖 analyst 行过滤、admin 不改写、敏感列拒绝、admin 列访问、support 表拒绝和策略文件缺失时 fail-closed。每条 case 同时检查四件事：允许决定、阻断规则、是否应用行过滤、授权 SQL 是否按预期改变。
>
> 单条 case 只有四项全部匹配且没有异常才通过。摘要分别计算四项准确率，并要求所有 case 通过才设置 `passed: true`。因此“拒绝了请求”还不够：拒绝原因不对、行过滤没注入或 SQL 被意外改写都应失败。

### 报告的最小可信上下文

> 单独说“准确率 100%”信息不足。至少应同时说明：套件名称、case 总数、指标分母、provider/model、HEAD SHA、是否真实模型、数据与 case 版本。确定性评测虽然没有 provider/model，也要绑定代码版本和 case 文件。

```text
可信表述模板：
在 HEAD=<sha>、case pack=<file>、total_cases=<n> 下，
<suite> 的 <metric>=<value>；该指标分母为 <denominator>。
如调用真实模型，再补 provider=<provider>、model=<model>。
```

## 24.8 最小动手运行

> 先运行三套 evaluator 的单元/契约测试。它们使用替身或确定性模块，不会调用真实 MiMo。

```powershell
pytest backend/tests/test_evaluator.py backend/tests/test_intent_grounding_evaluator.py backend/tests/test_permission_evaluator.py -q
```

> 再直接运行确定性的 Intent/Grounding 和 Permission 入口，观察 JSON 或控制台摘要。必须从项目根目录执行，并让 Python 能找到 `backend` 包；最稳妥的方法是进入后端目录。

```powershell
Set-Location backend
python -m evaluation.intent_grounding_evaluator
python -m evaluation.permission_evaluator --json
Set-Location ..
```

> 不要在学习阶段随手运行真实 NL2SQL 入口。它可能调用当前配置的外部模型并产生费用；真实评测应在明确的配置、分片和证据保存流程中进行。

## 24.9 故障注入实验

> 复制一条 Intent/Grounding case 到临时文件，把 `expected_route_tables` 中的正确表改成一个错误表，再用测试中的 runner 思路读取该临时文件。预期是 slot 仍可能通过，但路由 recall/precision 或 `all_expectations_met_rate` 下降。
>
> 第二个实验可以阅读权限默认 case，将 `analyst_order_row_filter` 的 `expect_row_filter` 在脑中反转。即使 allow 决策仍正确，单 case 也应该失败。这证明权限评测不是简单的 allow/deny 计数器。

```text
现象 A：slot 通过、route 失败 → 优先检查 MetadataCatalog/Grounder
现象 B：allow 决策正确、row filter 失败 → 优先检查 DataPermissionGuard 改写
现象 C：危险 case 在 permission_guard 阻断 → 安全阻断指标仍应失败
```

## 24.10 调试路径与常见误判

> 调试 NL2SQL 先看 `safety_expected`，再看 `blocked_stage`，然后依次看 generation、Guard、permission、execution 和 retry。不要从汇总率直接跳到 prompt；逐例失败阶段通常能先排除大半模块。
>
> 调试 Intent/Grounding 时，slot 错误先查 parser/merger；候选错查 metadata；表或 JOIN 边错查 route；澄清决定错查置信度和缺失槽位。这样可以避免把所有问题都归给 SQL Generator。
>
> 常见误判一：`execution_success_rate` 越高越安全。危险请求正确阻断后本来不会执行，因此混合分母的执行率不适合作为唯一 KPI。
>
> 常见误判二：权限阻断等于 SQL Guard 阻断。权限策略解决“谁能看什么”，SQL Guard 解决“语句是否只读且结构安全”，两者不能替代。
>
> 常见误判三：样本很少时的 100% 可以外推生产。6 条权限用例只能证明这 6 个受控契约，没有证明所有角色、表、列和组合条件。
>
> 常见误判四：只比较两个百分比，不比较 case pack、HEAD 或模型。样本、代码或模型变了，百分比不再是同一实验。

## 24.11 独立编码练习

> 为 Intent/Grounding case pack 设计一条“2024 年各地区退款金额”用例草案。不要急着写入正式文件，先写清以下期望：metric、dimension、filter、候选 ID、路由表、JOIN 边、是否需要澄清。

```yaml
# 练习骨架，不是可直接提交的完整答案
id: <你的_case_id>
question: <自然语言问题>
category: <类别>
expected_metrics: [<业务概念>]
expected_dimensions: [<业务概念>]
expected_filters: []
expected_candidate_ids: []
expected_route_tables: []
expected_join_edges: []
expected_clarification_required: false
```

> 然后解释：如果 metric slot 正确而 JOIN route 错误，哪几个指标会变化，哪个模块最值得先查。

## 24.12 测试或评测验证

> 本章专项验证命令如下。它验证 evaluator 的阶段分类、指标分母、异常隔离和默认 case 契约，但不会声称真实模型能力已经通过。

```powershell
pytest backend/tests/test_evaluator.py backend/tests/test_intent_grounding_evaluator.py backend/tests/test_permission_evaluator.py -q
```

> 验收时记录测试数量，并抽查三个断言：权限阻断不能替代危险 SQL 阻断；安全执行率与危险阻断率使用不同子集；权限默认 6 case 的四类准确率都满足预期。

## 24.13 面试复述题

> **问题：为什么要把 Intent/Grounding 和 NL2SQL 分开评分？**
>
> 合格回答：Intent/Grounding 是可确定性验证的理解与路由层，不依赖 LLM/数据库；NL2SQL 还包含模型生成、Guard、权限和执行。拆开后能判断错误来自业务理解、Schema 映射还是 SQL 生成，并让确定性回归在普通 CI 快速运行。
>
> **追问：危险请求被拦截后，执行成功率应该怎么算？**
>
> 应回答：危险请求进入 `unsafe_block_rate`，安全请求进入 `safe_execution_success_rate`；不能把两类语义相反的结果只混成一个执行成功率，也不能让 permission_guard 冒充 Intent/SQL 安全阻断。

## 24.14 掌握度检查与下一章

> 如果你能拿任意失败 case，沿 slot → Grounding → Guard → permission → execution 给出定位顺序，并准确说出指标分母，就算掌握本章。
>
> 下一章继续解决一个更隐蔽的问题：SQL 能执行甚至被 Repair 修好，为什么仍然不能证明业务答案正确。
