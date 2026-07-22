# 第29章 实战一：新增业务指标

> 本章预计 1～2 小时完成设计，再用 1～2 小时自行实现。练习目标是新增“净支付金额”，但本章不会给出可直接粘贴的完整补丁；你需要按契约逐层完成。

## 29.1 学习目标

> 完成本章后，你应该能够：
>
> - 在写代码前定义指标口径、时间口径、粒度和空值规则；
> - 识别 payments 与 refunds 直接 JOIN 的重复聚合风险；
> - 让别名解析、语义配置、Grounding、SQL Generator 和结果列契约一致；
> - 把“指标可计算”和“当前角色有权读取”分开设计；
> - 用确定性语义测试、权限测试和黄金结果 case 证明改造；
> - 列出回滚面，而不是只删除一行 Prompt。

## 29.2 前置知识

> 你已经掌握电商八表 Schema、Intent、语义层、Grounding、权限 Guard 和结果正确性评测。建议先复习第 3、9～11、16、24～25 章。

## 29.3 为什么需要这一模块

> 真实 Agent 需求很少只改一个函数。“新增净支付金额”至少涉及业务口径、物理列、自然语言别名、JOIN 路由、权限、生成上下文、黄金结果和展示。只改 Prompt 可能让某个问法偶然成功，却无法保证同义问法、分组、角色和回归稳定。
>
> 这个指标还有两个刻意保留的难点。第一，payments 与 refunds 都通过 order_id 关联订单，若每单允许多条支付和多条退款，直接三表 JOIN 会形成乘法行数。第二，当前 analyst 权限不包含金额字段，因此生成正确 SQL 也会被权限层合法拒绝。

## 29.4 输入、输出与依赖

### 先写指标契约

> 开始编码前，把下面问题写成一页 ADR 或练习记录。任何一项不明确，都应先向业务方澄清。

| 问题 | 推荐练习口径 | 为什么必须明确 |
|---|---|---|
| 指标名 | `net_paid_amount` | 稳定英文 key 同时作为结果别名 |
| 中文名 | 净支付金额 | 用于自然语言召回 |
| 分子 | 成功支付金额合计 | 需明确 payment_status 范围 |
| 扣减项 | 已发生退款金额合计 | 需明确退款状态；当前表没有状态列 |
| 时间 | 支付时间、退款时间还是订单时间 | 三者会产生不同报告 |
| 粒度 | 先按 order_id 聚合，再做外层统计 | 避免 payment × refund 重复 |
| 空值 | 没有支付/退款按 0 处理 | 需要 COALESCE |
| 角色 | 默认仅 admin，是否开放 analyst 待审批 | 权限不能被指标配置暗中绕过 |

> 为适配当前语义层的默认时间规则，本练习可先选择“按订单时间归属”，但必须在 description 中写明。若业务要求支付/退款各按自身发生时间归属，现有单一默认时间字段模型可能需要扩展，而不是硬塞一段复杂 SQL。

### 预期输出

> 改造完成后，明确问题应得到结构化 Intent，Grounding 选出稳定 candidate，生成 SQL 通过 Guard；admin 可执行并与黄金结果一致；analyst 在未变更策略时应得到可解释的权限拒绝。只有经过业务授权修改策略后，analyst 才能读取相关金额列。

## 29.5 执行流程

```text
定义业务口径与威胁边界
  → 检查物理 Schema 和数据粒度
  → 设计稳定 metric key / candidate_id / aliases
  → 扩展语义配置
  → 验证规则 Intent 召回
  → 验证 Grounding 候选、列和 JOIN route
  → 决定权限策略：保持拒绝或显式授权
  → 检查生成 Prompt 中的语义摘要
  → 用 Fake LLM 验证 SQL 契约
  → 增加黄金 reference SQL 与固定断言
  → 验证 API/前端列、表格、图表和审计事件
  → 跑旧指标回归
```

> 不建议第一步就运行真实模型。前六步都可以用确定性测试完成，先把业务契约和元数据链路做对，真实模型只用于最后的兼容冒烟。

## 29.6 当前代码地图

| 改造面 | 路径 | 需要回答的问题 |
|---|---|---|
| 物理 Schema | `database/init.sql` | paid/refund 字段和外键是什么 |
| 种子数据 | `database/seed_data.py` | 状态、零值和每单记录数假设 |
| 语义配置 | `backend/app/semantic/ecommerce_metrics.yaml` | key、别名、表达式、表、JOIN、说明 |
| 语义加载 | `backend/app/semantic/semantic_loader.py` | 配置如何进入 Prompt |
| 规则 Intent | `backend/app/analysis_intent/rule_parser.py` | aliases 如何召回 concept |
| Grounding | `backend/app/agents/grounding.py` | 候选的表、列和路由 |
| 权限策略 | `backend/app/security/data_permissions.yaml` | 哪些角色能读金额列 |
| 权限执行 | `backend/app/security/data_permission.py` | 最终 SQL AST 如何被授权 |
| 分层 cases | `backend/evaluation/cases/intent_grounding_cases.yaml` | 同义问法与 route 期望 |
| 黄金 cases | `backend/evaluation/cases/golden_result_cases.yaml` | 业务结果 oracle |
| 前端展示 | `frontend/src/components/` | 标量/分组结果如何显示 |

## 29.7 关键代码理解

### 物理事实：字段存在不等于可以直接相减

> 当前 `payments` 有 `paid_amount`、`payment_status`、`paid_at`，`refunds` 有 `refund_amount`、`refund_date`。两表都通过 `order_id` 关联 orders，但 Schema 没有声明一单只能有一条支付或退款。
>
> 因此下面这种思路在多支付、多退款时会重复金额，不应直接作为黄金口径。

```sql
-- 反例：只用于识别粒度风险
SELECT SUM(p.paid_amount) - SUM(r.refund_amount)
FROM orders o
JOIN payments p ON o.order_id = p.order_id
LEFT JOIN refunds r ON o.order_id = r.order_id;
```

> 更稳妥的业务 oracle 是先分别按 order_id 聚合支付和退款，再连接订单并做外层求和。具体是否只计 `payment_status = 'Paid'`，必须与种子数据和业务定义一致。

```text
payment_by_order(order_id, paid_total)
refund_by_order(order_id, refund_total)
orders LEFT JOIN 两个按订单聚合的结果
SUM(COALESCE(paid_total, 0) - COALESCE(refund_total, 0))
```

### 语义层边界：简单 expression 可能不够

> 当前 YAML 指标主要提供单个聚合 expression、source tables/columns、required joins 与少量 dimension override。复杂的“先聚合后 JOIN”未必能靠一条 expression 安全表达。
>
> 你有两个合理学习路径：
>
> - 初级路径：先新增“退款金额”这种单表聚合指标，完整走通跨层流程；
> - 进阶路径：为语义层设计可审查的 CTE/template contract，再实现净支付金额。
>
> 不合理路径是把任意完整 SQL 字符串塞进 expression，让 Prompt 看似知道答案，却绕过 Grounding、权限列提取或维度组合规则。

### 稳定身份：key、candidate_id 与 alias 各司其职

> `net_paid_amount` 是内部 concept 与推荐输出别名；`candidate_id` 用于 Grounding/澄清稳定引用；中文名和“实收金额”“支付净额”等 alias 用于召回。三者不能随意互换，也不要给同一 alias 配置多个指标造成歧义。

> Rule parser 会从 MetadataCatalog 的 key/name/aliases 中按文本位置召回，因此通常不需要新增硬编码 if。修改 YAML 后，应先证明规则 parser 已识别，再证明 Grounder 能找到候选。

### 权限默认不放宽

> 当前 analyst 的 payments 列不含 `paid_amount`，refunds 列不含 `refund_amount`；support 甚至无权访问这两张表。admin 使用通配权限。
>
> 所以最安全的第一版验收是：admin 正确执行，analyst 被 `block_unauthorized_column` 拒绝，support 被表/列规则拒绝。只有业务明确授权后，才能在 YAML 中加入金额列，并补“应允许”和“仍应拒绝”的对照测试。

> 语义层声明指标绝不能自动提升权限。权限 Guard检查最终 SQL AST，这正是 Agent 面试项目的重要工程边界。

### 黄金 case 才能证明业务口径

> 语义和 Grounding 测试证明“知道该用哪些概念与表”，SQL Guard证明“语句安全”，执行成功证明“数据库接受”，只有黄金 reference SQL 与结果比较才能证明“指标值符合定义”。
>
> 如果固定数据允许，增加 scalar fixed assertion；若数据会变化，至少锁定 required columns、comparison mode 和人工审核的 reference SQL，并记录数据库快照版本。

## 29.8 最小动手运行

> 先运行现有语义、MetadataCatalog、Grounding 和权限测试，建立改造前基线。

```powershell
pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py backend/tests/test_schema_grounding_precision.py backend/tests/test_data_permission_guard.py -q
```

> 修改后先重复同一命令，再运行 Intent/Grounding 与结果正确性 evaluator 测试。

```powershell
pytest backend/tests/test_intent_grounding_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
```

> 这些命令不需要真实模型。只有所有确定性契约通过后，才考虑对 admin 做一个非敏感真实模型冒烟。

## 29.9 故障注入实验

> 故意让 alias 召回 concept `net_paid_amount`，但 YAML candidate_id 或 evaluator 仍写旧名字。观察 Rule parser 可能通过，而 Grounding case 的 candidate 期望失败。恢复后记录哪个稳定标识发生漂移。
>
> 第二个实验：在临时 reference SQL 中直接 JOIN payments 与 refunds，再与“分别按 order_id 预聚合”的 reference 比较。在构造一单两支付两退款的 fixture 时，两者结果应不同，从而证明粒度风险。
>
> 第三个实验：不改权限策略，用 analyst 运行包含金额列的固定 SQL。预期是权限拒绝且 QueryRunner 不被调用；不要为了让测试变绿去绕过 Guard。

## 29.10 调试路径与常见误判

> 推荐顺序：业务定义 → Schema/粒度 → alias/Intent → candidate/Grounding → route → SQL 列与 JOIN → permission → execution → golden result → frontend。
>
> 常见误判一：YAML 能加载就表示指标完成。还没有证明 alias、Grounding、权限、生成与结果。
>
> 常见误判二：SQL 执行成功就表示净额正确。多对多 JOIN 会生成合法但重复聚合的结果。
>
> 常见误判三：系统知道指标就应该允许 analyst 查。知识可见性与数据授权是两套契约。
>
> 常见误判四：把真实模型偶然生成的 CTE 当成稳定功能。需要确定性语义约束和黄金 case。
>
> 常见误判五：只加新 case，不跑旧指标。别名冲突、JOIN 图变化或权限放宽可能破坏销售额、退款率等既有契约。

## 29.11 独立编码练习

> 在独立分支完成以下清单。先做“退款金额”初级版，再决定是否扩展为“净支付金额”进阶版。

```text
[ ] 一页指标契约：口径、粒度、时间、空值、角色
[ ] 语义 key/name/aliases/candidate_id 不冲突
[ ] source_tables/source_columns/required_joins 完整
[ ] Rule parser 同义问法测试
[ ] Grounding candidate、列和 route 测试
[ ] admin/analyst/support 权限对照
[ ] 黄金 reference SQL 经人工审核
[ ] scalar/ordered/unordered 比较模式正确
[ ] 前端标量与分组展示检查
[ ] 旧指标回归
[ ] 风险和回滚说明
```

> 回滚不是只删 YAML。还要同步删除对应 case、测试期望、Prompt 快照、权限变更和文档，避免留下孤儿 contract。

## 29.12 测试或评测验证

> 最低验收矩阵如下：

| 维度 | 至少覆盖 |
|---|---|
| 语言 | 中文名、英文 key、一个业务别名 |
| 查询形态 | 标量、按月或按地区分组 |
| 权限 | admin 允许、analyst 默认拒绝、support 拒绝 |
| 结果 | 黄金 SQL、完整列、值、必要 fixed assertion |
| 安全 | 最终 SQL 仍过 SQL Guard 与权限 Guard |
| 回归 | 现有销售额、退款率、客单价 |

```powershell
pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py backend/tests/test_schema_grounding_precision.py backend/tests/test_data_permission_guard.py backend/tests/test_intent_grounding_evaluator.py backend/tests/test_result_correctness_evaluator.py -q
```

> 验证报告要分别写“确定性链路通过”和“真实模型冒烟结果”；没有完整真实评测时不能说该指标对所有自然语言问法都稳定。

## 29.13 面试复述题

> **问题：新增一个业务指标为什么不能只改 Prompt？**
>
> 合格回答：指标需要稳定业务口径、物理粒度、语义别名、Grounding candidate/JOIN route、最终 SQL 权限、黄金结果和前端展示。Prompt 只是模型上下文，不能替代确定性授权与结果 oracle。
>
> **追问：净支付金额最容易踩什么坑？**
>
> 应回答：payments 与 refunds 都可能对订单一对多，直接 JOIN 会乘法重复；应先按 order_id 分别聚合。还要明确状态和时间口径，并注意 analyst 当前无金额列权限，不能因新增指标自动放宽。

## 29.14 掌握度检查与下一章

> 如果你能在不看代码时列出至少 8 个改造面，并能解释“正确 SQL但权限拒绝”为什么可能是预期结果，就算掌握本章。
>
> 下一章进入调试实验室：同一个“没有结果”表象，可能来自工作目录、Schema、权限或 LLM 空 content 四种完全不同的根因。
