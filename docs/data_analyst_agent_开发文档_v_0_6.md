# Data Analyst Agent 开发文档 v0.6

## 版本定位

v0.6 将项目从“可安全执行的 NL2SQL Agent”推进到“可解释、可澄清的分析意图理解 Agent”。核心变化是：不再把用户问题直接交给 SQL Generator 猜表和字段，而是在 SQL 生成前先产出结构化分析意图，再做 Schema Grounding，并在明显模糊且缺关键槽位的问题上主动暂停澄清。

## 核心链路

```text
用户问题
  -> Intent Guard
  -> Analysis Intent Parser
  -> Schema Grounding
  -> Clarification Decision
      -> clarification_required: 返回 candidate_id 候选并暂停
      -> completed: 加载 Schema 并生成 SQL
  -> SQL Guard
  -> Query Runner / SQL Repair
  -> SQL Optimizer
  -> Answer Generator
```

## 新增能力

### 1. 分层分析意图

`backend/app/analysis_intent/` 负责把自然语言问题转换为稳定结构：

- `metrics`：销售额、订单数、退款率等业务指标。
- `dimensions`：地区、月份、商品类别等分析维度。
- `filters`：年份、时间范围等过滤条件。
- `ranking`：Top-N 和排序方向。
- `missing_slots`：缺失但执行分析必需的信息。
- `conflicts`：规则解析和 LLM 解析不一致时保留冲突，不静默覆盖。

规则解析器负责高确定性槽位，LLM 解析器补充复杂或隐式意图，合并器保留冲突并降低置信度。

### 2. Schema Grounding

`backend/app/agents/grounding.py` 将业务概念映射到语义层定义的表达式、候选 ID、所需表和字段。每个候选使用稳定 `candidate_id`，便于后续澄清、评测和审计。

示例：

```json
{
  "candidate_id": "sales_by_order_total",
  "concept": "sales_amount",
  "expression": "SUM(orders.total_amount)",
  "tables": ["orders"],
  "columns": ["orders.total_amount"]
}
```

### 3. 主动澄清闭环

当问题明显模糊且缺少关键指标，或规则/LLM 意图候选冲突时，AgentGraph 会在 SQL 生成前暂停：

- 不加载业务 Schema。
- 不调用 SQL Generator。
- 不访问数据库。
- 返回 `status=clarification_required`。
- 返回 `clarification.options[].candidate_id`。

前端点击候选后，会把 `clarification_id` 和 `clarification_candidate_id` 发回 `/api/chat/query`。后端用 `SessionStore` 找回冻结的原始问题，将候选归一化为稳定 ID 后重新进入完整 Agent 流程。

### 4. 前端交互调整

前端工作台不再首屏自动提交真实查询，避免打开页面即消耗 Qwen 调用。用户主动点击“开始分析”后才触发 Agent。右侧意图面板展示澄清候选，点击候选会提交结构化恢复请求。

## API 契约变化

`POST /api/chat/query` 请求新增可选字段：

```json
{
  "question": "销售额",
  "session_id": "demo-session",
  "clarification_id": "clarify_0001",
  "clarification_candidate_id": "metric_sales_amount",
  "clarification_text": null
}
```

响应新增字段：

```json
{
  "status": "clarification_required",
  "clarification": {
    "clarification_id": "clarify_0001",
    "question": "您想分析什么指标？",
    "options": [
      {
        "candidate_id": "metric_sales_amount",
        "label": "销售额",
        "description": "分析销售额相关的数据"
      }
    ]
  }
}
```

`status` 取值：

- `completed`：分析完成。
- `blocked`：Intent Guard 或 SQL Guard 阻断。
- `clarification_required`：需要用户补充信息。
- `clarification_expired`：澄清请求过期或候选无效。

## LangGraph 节点拆分

v0.6 主链路已经将意图、Grounding 和澄清决策拆成独立节点：

- `parse_intent`：只负责规则意图、LLM 意图和候选合并。
- `ground_schema`：只负责将结构化意图映射到业务表达式、候选和路由证据。
- `assess_clarification`：只负责判断是否暂停并返回澄清候选。

这样做的目的不是增加复杂度，而是让每一层都有清晰输入输出，便于测试、审计和面试讲解。

## 当前验证

- 后端全量测试：`367 passed`。
- 前端生产构建：通过，保留 Element Plus 和 ECharts 大 chunk 警告。
- Secret Scan：扫描 212 个 tracked files，通过。
- Intent Evaluation：37 条 case 全部通过。
- v0.6 分层意图/Grounding Evaluation：7 条 case 全部通过，槽位整体匹配率、Grounding 候选命中率、路由表召回率、澄清决策准确率和澄清候选命中率均为 `100%`。

## 面试讲法

v0.6 可以重点讲三点：

1. **从黑盒生成到分层可解释**：SQL 生成前先展示结构化意图和 Grounding 证据。
2. **从猜测执行到主动澄清**：缺关键指标时暂停，不让 LLM 硬猜 SQL。
3. **从能跑到可证明**：用 350+ 测试、固定评测集和黄金正确性基准证明安全、修复和业务口径。

## 后续方向

- 扩充分层意图/Grounding 专用评测集，加入更多口语化、多意图和冲突候选 case。
- 接入 Spider、BIRD 等公开数据集，验证跨领域泛化能力。
- 将 LLM 调用指标持久化到时序存储，做长期质量和成本监控。
