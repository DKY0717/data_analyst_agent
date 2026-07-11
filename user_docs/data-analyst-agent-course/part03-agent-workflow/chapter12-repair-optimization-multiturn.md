# 第十二章 SQL 自动修复、优化与多轮分析

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 12.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 区分网络重试、SQL 修复重试和用户重新提问；
> 2. 说明错误分类如何选择差异化修复策略；
> 3. 理解修复后重新经过 Guard 和权限的必要性；
> 4. 解释 SQL Optimizer 为什么先看 AST 和结果，再决定是否执行 EXPLAIN；
> 5. 说明多轮上下文为什么只保存摘要而不是完整结果行；
> 6. 理解澄清请求如何保存、恢复和消费；
> 7. 使用测试验证修复、优化和会话隔离行为。

## 12.2 问题场景：SQL 执行失败后的恢复

> SQL 执行失败不一定表示用户问题无法回答。模型可能写错列名、表名、函数、类型或聚合结构；这些错误可以把数据库反馈给修复 Agent，再尝试一次。但修复本身也是一次模型输出，必须受到与第一次 SQL 相同的安全边界约束。
>
> 工作流中的 `retry_count` 记录业务修复次数，默认最多 3 次。它与 LLM HTTP 客户端内部的网络重试不同：前者改变 SQL，后者只是重复发送同一请求。

## 12.3 错误分类驱动修复

### 12.3.1 分类结果

> `SQLRepairAgent.repair()` 先调用 `classify_sql_error(error_message, error_type)`，再从 `_REPAIR_STRATEGIES` 选择 Prompt 后缀和温度。错误分类器只提取稳定类别和必要目标，不把所有数据库原文直接暴露给模型或用户。

| 类别 | 修复重点 |
|---|---|
| `COLUMN_NOT_FOUND` | 对照 Schema 修正列名、补充表别名 |
| `TABLE_NOT_FOUND` | 修正表名或补充必要 JOIN |
| `FUNCTION_NOT_FOUND` | 使用 DuckDB 支持的等效函数 |
| `TYPE_MISMATCH` | 增加合适的 `CAST` 或统一日期类型 |
| `AGGREGATE_MISUSE` | 调整 `GROUP BY` 或聚合表达式 |
| `SYNTAX` | 修复括号、逗号、方言和 LIMIT 语法 |
| `AMBIGUOUS_COLUMN` | 为 JOIN 字段补充表别名 |
| `TIMEOUT` | 缩小过滤范围、减少扫描和 JOIN |

### 12.3.2 为什么不使用一个万能 Prompt

> “字段不存在”和“查询超时”的修复方向不同。前者需要核对 Schema，后者可能需要增加时间过滤；把错误类别传入差异化策略，可以减少模型做无关改写，也更容易评测每类错误是否修复成功。

## 12.4 SQLRepairAgent 的输入和输出

```python
result = await llm_client.repair_sql(
    original_sql=original_sql,
    error_message=error_message,
    schema_info=schema_str,
    system_suffix=strategy["system_suffix"],
    temperature=strategy["temperature"],
)

return SQLRepairOutput(
    repaired_sql=result["repaired_sql"],
    repair_reason=repair_reason,
)
```

> 修复 Agent 收到原 SQL、错误信息、Schema 和分类策略，返回 `repaired_sql` 与稳定的 `repair_reason`。它不接收用户的认证 Token，也不应该自行执行 SQL。执行权限仍然属于工作流后面的确定性节点。

## 12.5 修复闭环和安全不变量

```text
execute_sql 失败
  ↓ retry_count < SQL_MAX_RETRIES
repair_sql 调用 LLM
  ↓
generated_sql 更新
  ↓
validate_sql 重新校验
  ↓
authorize_sql 重新检查权限
  ↓
execute_sql 再次执行
```

> 修复后必须回到 `validate_sql`，因为新 SQL 可能被模型改成 `DELETE`、文件函数或超大查询。通过 SQL Guard 后还必须再次检查数据权限，因为修复可能新增表、字段或 JOIN。不能用“原 SQL 曾经安全”推断“修复 SQL 仍然安全”。

## 12.6 重试耗尽和用户可见状态

> 当 `retry_count` 达到 `SQL_MAX_RETRIES` 时，`_should_continue()` 返回 `end`。系统保留失败阶段、重试次数和稳定错误信息，不继续调用模型无限修复。API 仍然返回稳定的 `QueryResponse` 字段，前端可以提示用户换一种问法。

| 状态 | 含义 | 是否进入 Repair |
|---|---|---|
| SQL Guard blocked | SQL 不安全 | 否 |
| Permission blocked | 越权 | 否 |
| Execution failed, retries left | 通过安全和权限但数据库执行失败 | 是 |
| Execution failed, retries exhausted | 已达到业务上限 | 否 |

## 12.7 SQL Optimizer 的规则化建议

> `SQLOptimizer.optimize()` 只接收已经成功执行的 SQL 和结果。它先从 SQL AST 识别 `SELECT *`，再根据结果行数判断是否达到上限；只有没有发现明显问题时，才额外执行经过 SQL Guard 的 `EXPLAIN`。

```python
if not query_result.get("success"):
    return []

suggestions.extend(self._suggest_from_sql_shape(sql))
suggestions.extend(self._suggest_from_result_size(query_result))

if not suggestions:
    plan_text = self._load_explain_plan(sql)
    suggestions.extend(self._suggest_from_plan(plan_text))
```

> 这种顺序控制了额外数据库调用：如果 SQL 已经有明显问题，先给出规则建议；只有需要执行计划时才运行 EXPLAIN。EXPLAIN 也会重新经过 Guard，避免优化器成为安全绕过路径。

### 12.7.1 优化建议不是自动改写

> 当前优化器返回可解释的建议，例如避免 `SELECT *`、增加时间过滤或检查顺序扫描，并不会自动修改原 SQL。自动改写会改变结果语义，应该在有独立验证和回归测试时再考虑。

## 12.8 多轮上下文为什么要压缩

> 用户可能先问“统计 2024 年每个月销售额”，再问“按地区拆一下”。第二轮需要继承指标和时间范围，但不需要把上一轮全部结果行重新塞进 Prompt。

```python
return {
    "question": final_state.get("question") or "",
    "sql": final_state.get("validated_sql") or final_state.get("generated_sql") or "",
    "columns": query_result.get("columns", []),
    "row_count": query_result.get("row_count", 0),
    "answer_summary": self._truncate(final_state.get("answer") or ""),
    "optimization_suggestions": final_state.get("optimization_suggestions", []),
    "success": True,
}
```

> `ConversationContextBuilder` 保留问题、最终 SQL、列名、行数、答案摘要和优化建议，不保存完整 `rows`。这样可以控制 Prompt 长度，减少敏感数据重复传播，也让模型关注分析意图而不是复制历史表格。

## 12.9 SQLiteSessionStore 的会话持久化

> `SQLiteSessionStore` 将每轮摘要保存在 `data/sessions.db` 的 `session_turns` 表中，并只保留最近 `max_turns` 轮。每个线程使用独立连接，开启 WAL 以改善并发读写；会话 ID 是隔离不同用户上下文的关键。

```text
session_id
  ↓
读取最近几轮 turn_data
  ↓
按时间顺序恢复
  ↓
ConversationContextBuilder.build_context()
  ↓
注入 SQL Generator Prompt
```

> 无 `session_id` 时，系统保持单轮查询行为，不读取历史，也不写入会话。权限阻断的轮次不会进入多轮上下文，避免下一轮 Prompt 继承越权字段或表名。

## 12.10 失败轮和成功轮的记录边界

> 成功轮保存列名、行数和答案摘要；执行失败轮只保存问题、SQL 和错误摘要；Intent Guard 阻断、SQL Guard 阻断和权限阻断不能被当作普通分析上下文写入。不同状态的保存规则是数据安全和多轮正确性的组成部分。

## 12.11 澄清请求的保存与恢复

> 当图在 `assess_clarification` 节点暂停时，`AgentGraph.run()` 会把原问题和 `clarification_request` 保存到 `pending_clarifications`。用户提交 `clarification_id` 与候选 ID 后，SessionStore 校验请求是否匹配，再把候选标签追加到原问题中重新执行。

```text
原问题 + clarification_id + candidate_id
  ↓
按 session_id 找到 pending 请求
  ↓
校验 clarification_id 和候选
  ↓
消费 pending 记录
  ↓
原问题 + “用户澄清：候选”
  ↓
重新进入 AgentGraph
```

> 候选恢复优先使用稳定的 `candidate_id`；自由文本也必须归一化到已有候选，不能让用户通过任意文本绕过澄清选项。找不到请求、ID 不匹配或候选无效时，系统返回 `clarification_expired`，不会继续调用下游依赖。

## 12.12 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/agents/sql_repair.py` | 分类并调用修复模型 | 策略、结构化输出、错误边界 |
| `backend/app/security/error_classifier.py` | 归类 SQL 执行错误 | Repair 策略选择 |
| `backend/app/agents/sql_optimizer.py` | 生成规则化优化建议 | AST、结果规模、EXPLAIN |
| `backend/app/agents/conversation_context.py` | 压缩多轮上下文 | 摘要字段、长度限制、失败轮 |
| `backend/app/agents/session_store.py` | SQLite 会话和澄清持久化 | 最近轮次、候选恢复、隔离 |
| `backend/tests/test_sql_repair.py` | 修复行为测试 | 成功、格式错误和异常 |
| `backend/tests/test_sql_optimizer.py` | 优化建议测试 | SELECT *、行数和 EXPLAIN |
| `backend/tests/test_conversation_context.py` | 上下文测试 | 不保存完整结果行 |
| `backend/tests/test_session_store.py` | 会话测试 | 会话隔离和澄清恢复 |

## 12.13 动手验证

> 运行修复、优化和上下文测试：

```bash
pytest backend/tests/test_sql_repair.py backend/tests/test_sql_optimizer.py backend/tests/test_conversation_context.py backend/tests/test_session_store.py -q
```

> 再运行工作流测试，确认修复会回到 Guard，权限阻断不会进入 Repair：

```bash
pytest backend/tests/test_agent_graph.py -q
```

> 这些测试使用 Mock 或隔离数据库，不需要真实模型额度。真实 LLM Repair 评测应使用项目提供的评测入口，并明确记录模型、用例和失败类别。

## 12.14 常见错误

### 把网络重试算成 SQL 修复

> HTTP 客户端重试同一请求，SQL Repair 会生成新的 SQL；二者的成本、上限、审计意义都不同。应分别观察 API attempt count 和 Agent retry_count。

### 修复后直接执行

> 这是最危险的实现错误之一。修复模型可能引入写操作、越权字段或文件函数，必须重新经过 Guard 和权限层。

### 把完整结果行保存到 session

> 这会造成 Prompt 膨胀和数据重复暴露。只保存能帮助理解追问的摘要字段，并限制答案摘要长度。

### 用用户自由文本直接恢复澄清

> 任意文本可能改变原任务或注入新的意图。自由文本只能匹配已有候选，无法匹配时应拒绝恢复。

### 每次优化都执行 EXPLAIN

> EXPLAIN 是额外数据库调用，并可能增加延迟。当前实现先检查 AST 和结果规模，再在没有明显建议时执行，并且 EXPLAIN 也要过 Guard。

## 12.15 本章小结

> 自动修复让系统能够从可恢复的执行错误中继续推进，但它不是安全豁免；优化器提供解释性建议，而不是未经验证的自动改写；多轮上下文通过摘要和 SQLite 持久化帮助用户追问，同时控制长度和权限污染。三者共同把一次性查询变成更可靠、可观察、可恢复的分析流程。

## 12.16 练习

1. 为“字段不存在”和“查询超时”各写出一条不同的修复策略。
2. 追踪一次执行失败的 `retry_count`，说明它何时增加、何时停止。
3. 修改上下文构建器的 `max_turns`，观察 Prompt 中保留的轮次变化。
4. 构造一个无效 `clarification_id`，确认系统不会重新执行查询。
5. 解释为什么优化建议节点应该位于执行成功之后、答案生成之前。

## 12.17 下一章衔接

> 到这里，核心 Agent 已经能安全地理解意图、生成 SQL、处理失败并支持追问。下一部分会把“谁可以查询什么”加入执行链路，学习认证、表列权限、行级过滤和安全审计。
