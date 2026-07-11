# 第十章 语义层、Schema Grounding 与主动澄清

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 10.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释业务语义层为什么不能只靠数据库字段名；
> 2. 读懂 `ecommerce_metrics.yaml` 中指标、维度和 JOIN 的表达方式；
> 3. 说明 MetadataCatalog 如何合并物理 Schema 和语义配置；
> 4. 解释 Grounding 候选、来源表、来源字段和最短 JOIN 路径；
> 5. 理解为什么派生表达式不能被误判成物理表；
> 6. 说明何时应该主动澄清，而不是继续生成 SQL。

## 10.2 问题场景：业务词不等于字段名

> 用户说“退款率”，数据库里通常没有一个叫 `refund_rate` 的字段；用户说“按地区”，也不一定对应唯一的 `region_name`。一个业务指标可能涉及多张表、过滤条件、分母定义和时间口径。
>
> 语义层把这些业务规则显式配置下来，Grounding 再把结构化意图映射到真实表、字段、表达式和 JOIN 路径。这样模型负责组合 SQL，但关键业务口径不是临场猜出来的。

## 10.3 YAML 语义层

### 10.3.1 指标定义

> `backend/app/semantic/ecommerce_metrics.yaml` 为指标提供稳定 key、名称、别名、表达式、来源表、来源字段和说明。例如销售额的表达式可以使用 `orders.total_amount` 或订单明细金额，具体以当前配置为准。

```yaml
metrics:
  sales_amount:
    name: 销售额
    aliases:
      - 销售额
      - 销售金额
    expression: SUM(orders.total_amount)
    default_table: orders
    description: 订单主表中的订单总金额汇总。
```

> 稳定 key 用于程序内部传递，中文名称和别名用于召回，表达式和来源表用于 SQL 生成和路由。修改指标口径时，应该更新语义配置、评测基准和相关文档，而不是只修改 Prompt。

### 10.3.2 维度和时间粒度

```yaml
dimensions:
  month:
    candidate_id: order_month
    name: 月份
    aliases:
      - 月份
      - 按月
    fields:
      - strftime(orders.order_date, '%Y-%m')
```

> 维度可以是物理列，也可以是从日期派生的表达式。语义层还可以声明季度、地区、商品类别和支付方式，并通过 `required_joins` 说明到达目标字段需要经过哪些关系。

### 10.3.3 全局 JOIN 图

```yaml
joins:
  - left: orders.customer_id
    right: customers.customer_id
  - left: customers.region_id
    right: regions.region_id
```

> 指标或维度只声明终点表还不够，SQL 需要知道中间表如何连接。全局 JOIN 图让 Grounding 可以在表级图上寻找最短路径，并把字段级连接边交给 SQL Generator。

## 10.4 SemanticLoader 的职责

> `SemanticLoader` 负责读取和查询 YAML 语义配置。它提供按 key、名称或别名查找指标和维度的方法，也提供 `format_for_prompt()` 把语义摘要交给 SQL Generator。

```text
ecommerce_metrics.yaml
  ↓
SemanticLoader
  ├─ get_metrics()
  ├─ get_dimensions()
  ├─ find_metric(concept)
  ├─ find_dimension(concept)
  └─ get_joins()
```

> Loader 不负责执行 SQL，也不直接判断用户是否有权限。它只是把业务定义以稳定 API 暴露给解析和 Grounding 模块。

## 10.5 MetadataCatalog：建立统一元数据视图

```python
@classmethod
def from_sources(cls, schema=None, semantic=None):
    physical_schema = schema if schema is not None else schema_loader.get_full_schema()
    semantic_source = semantic or semantic_loader
    return cls(
        tables=physical_schema.get("tables", {}),
        metrics=semantic_source.get_metrics(),
        dimensions=semantic_source.get_dimensions(),
    )
```

> `MetadataCatalog` 把数据库真实结构和业务语义放入同一份只读视图，并使用深拷贝避免下游裁剪上下文时污染全局对象。测试可以注入隔离 Schema 和语义数据，生产则使用全局 Loader。

### 10.5.1 候选召回

> `find_metric_candidates()` 和 `find_dimension_candidates()` 会用稳定 key、名称和 aliases 做不区分大小写的精确匹配，并按 key 排序保证结果稳定。这里是确定性召回，不是模糊向量搜索；没有匹配时返回空列表，让上游决定是否澄清。

## 10.6 Grounding 候选

### 10.6.1 指标 Grounding

> `SchemaGrounder._ground_metric()` 会先查语义层指标，再根据显式 `source_tables/source_columns` 或 SQL AST 推导来源。指标可能同时拥有默认表达式和按维度覆盖的表达式；当当前意图包含对应维度时，覆盖候选得分更高。

```json
{
  "concept": "sales_amount",
  "candidates": [
    {
      "candidate_id": "sales_amount_by_category",
      "expression": "SUM(order_items.quantity * order_items.unit_price)",
      "tables": ["order_items", "orders"],
      "columns": ["order_items.quantity", "order_items.unit_price"],
      "score": 1.0
    }
  ]
}
```

> 候选保留表达式、来源表、来源列、得分和证据，便于后续解释和评测。Grounding 不是只返回一个字符串；它还要回答“为什么选它、需要哪些表、路径是否完整”。

### 10.6.2 维度 Grounding

> 维度定义中的 `fields` 可能包含多个候选字段，例如地区可以对应 `regions.region_name`、`regions.province` 或 `regions.city`。当前实现把候选表达式和来源表保留在结果中，由下游结合问题上下文决定使用哪一个。

## 10.7 从表集合构建最短 JOIN 路径

> Grounding 会收集当前意图中得分最高候选的来源表，再对这些表两两查找 JOIN 图的最短路径。电商 Schema 的主图近似树状，因此路径并集可以得到覆盖目标表的最小连接子图。

```text
orders + regions
  ↓
orders.customer_id = customers.customer_id
  ↓
customers.region_id = regions.region_id
```

> 如果指标来源是 `orders`，维度来源是 `regions`，结果必须包含中间表 `customers`。只把 `orders` 和 `regions` 交给模型而不提供连接边，会迫使模型自行猜 JOIN，容易产生笛卡尔积或字段歧义。

### 10.7.1 路由置信度

> 当所有目标表都在 JOIN 图中连通时，`SchemaRoute.confidence` 可以为 1.0；如果找不到路径，则返回未连通状态。这个信号可以用于评测和澄清，而不应该被静默忽略。

## 10.8 防止派生表达式污染物理表集合

> 从 `SUM(orders.total_amount)` 这样的表达式提取来源表时，必须使用 SQL AST，而不是对字符串按 `.` 或括号切分。否则可能把 `SUM(orders` 当成表名，或者把派生别名当成真实物理表。

```python
parsed = sqlglot.parse_one(f"SELECT {expression}", dialect="duckdb")
return {
    column.table.lower()
    for column in parsed.find_all(exp.Column)
    if column.table
}
```

> 当前 Grounding 还优先使用语义层显式 `source_tables` 和 `source_columns`，只有缺失时才从 AST 推导。这种“配置优先、解析兜底”的策略可以让重要指标的物理来源更明确。

## 10.9 主动澄清

### 10.9.1 什么时候澄清

> `ClarificationEngine` 在整体置信度低于阈值，或意图存在缺失槽位时生成澄清请求。如果既没有候选选项，也无法给出有意义的选择，当前实现会返回 `None`，避免向用户展示空澄清。

```python
if intent.overall_confidence >= self.CONFIDENCE_THRESHOLD \
        and not intent.missing_slots:
    return None
```

> 澄清并不意味着所有模糊问题都必须暂停。多轮上下文存在时，后续节点可能继承最近一轮指标；系统需要把“真的缺少信息”和“用户在追问上一轮”区分开。

### 10.9.2 澄清候选

> 完全缺少指标时，当前引擎会提供销售额、订单数和客户数等候选；已有指标但缺少维度时，会提供地区、月份和商品类别等候选。每个候选都有 `candidate_id`、标签和说明，前端可以用 ID 恢复请求，而不是依赖自然语言猜测用户选择。

```json
{
  "clarification_id": "clarify_1234",
  "question": "您想分析什么指标？例如：销售额、订单数、退款率等。",
  "options": [
    {"candidate_id": "metric_sales_amount", "label": "销售额"}
  ],
  "max_rounds": 2
}
```

> `clarification_id` 当前使用问题哈希生成，适合演示和短生命周期请求；如果需要跨进程或长期保存，应该进一步使用持久化存储和更强的唯一 ID 策略。教程只描述当前实现，不把它包装成分布式澄清服务。

## 10.10 端到端 Grounding 流程

```text
AnalysisIntent
  ↓
MetadataCatalog 召回业务候选
  ↓
SchemaGrounder 生成表达式、表、字段和证据
  ↓
JOIN 图寻找最短连接路径
  ↓
置信度/缺失槽位检查
  ├─ 信息不足 → ClarificationRequest
  └─ 信息充分 → 注入 SQL Generator 上下文
```

## 10.11 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/semantic/ecommerce_metrics.yaml` | 电商指标、维度和 JOIN 配置 | 业务口径与物理来源 |
| `backend/app/semantic/semantic_loader.py` | 读取语义配置 | 召回和 Prompt 摘要 |
| `backend/app/schema_context/metadata_catalog.py` | 合并物理与语义元数据 | 深拷贝、候选召回、Join 边 |
| `backend/app/agents/grounding.py` | 生成 Grounding 结果 | 候选、来源、最短路径 |
| `backend/app/agents/clarification.py` | 生成澄清请求 | 置信度、缺失槽位、候选 |
| `backend/tests/test_semantic_loader.py` | 语义配置测试 | 指标、维度和 Join 读取 |
| `backend/tests/test_metadata_catalog.py` | 元数据目录测试 | 隔离来源和候选召回 |

## 10.12 动手验证

> 先运行语义和元数据测试：

```bash
pytest backend/tests/test_semantic_loader.py backend/tests/test_metadata_catalog.py -q
```

> 如果希望覆盖 Grounding 的路由行为，可以运行与意图集成相关的测试：

```bash
pytest backend/tests/test_analysis_intent_integration.py backend/tests/test_intent_grounding_evaluator.py -q
```

> 预期结果应证明：业务 key 能召回候选，地区路径包含 `customers` 中间表，派生指标不会被当成伪物理表。具体 case 以当前测试文件中的固定数据为准。

## 10.13 常见错误

### 只把指标表达式交给模型

> 表达式能说明如何计算，但不能保证模型知道所有连接表。应同时提供来源表、来源列和 JOIN 边。

### 把所有候选表都放进 SQL

> 未选中的候选会污染上下文，增加错误 JOIN 和笛卡尔积风险。当前实现只使用得分最高候选构建路由，同时保留完整候选用于解释和评测。

### 用字符串解析表达式中的表名

> 聚合函数、CTE、别名和嵌套表达式会让字符串切分产生伪表。应使用 SQLGlot AST，并优先使用语义层显式来源。

### 置信度低却继续生成 SQL

> 这会让系统把猜测包装成确定答案。先检查缺失槽位、冲突和路由连通性，再决定澄清或继续。

## 10.14 本章小结

> 语义层定义业务口径，MetadataCatalog 统一物理和业务元数据，Grounding 把概念映射到表达式、表、字段和 JOIN 路径，Clarification Engine 处理不可确定的问题。这个中间层让 SQL Generator 不必独自承担业务理解、数据库发现和用户交互三种责任。

## 10.15 练习

1. 在语义 YAML 中找到“商品类别”对应的 JOIN 路径，并画出经过的表。
2. 为一个指标补充 `source_tables`，说明它为什么比从表达式自动推导更稳定。
3. 构造一个指标表和维度表不连通的测试目录，观察 `SchemaRoute.confidence`。
4. 说明为什么“缺失指标”适合主动澄清，而不是默认选择销售额。
5. 对比“候选列表”和“最终路由”两个结果，它们分别服务于什么目的？

## 10.16 下一章衔接

> 到这里，系统已经有了安全意图、结构化意图和物理路由，但这些步骤还需要被可靠地串起来。下一章会用 LangGraph 把状态、节点、条件边和终止路径组织成完整 Agent 工作流。
