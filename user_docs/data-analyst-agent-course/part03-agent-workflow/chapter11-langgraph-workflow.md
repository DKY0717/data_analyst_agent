# 第十一章 使用 LangGraph 编排 Agent 工作流

> 本章对应项目版本 `v1.7`。本章最后核对日期为 2026-07-11。

## 11.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 解释为什么要用图而不是在 API 函数里堆叠所有步骤；
> 2. 理解 `AgentState`、节点、普通边和条件边；
> 3. 画出当前项目 12 个工作流节点的主路径；
> 4. 说明安全阻断、权限阻断和执行失败分别在哪里终止或回流；
> 5. 理解节点返回“状态增量”而不是直接修改共享状态的原因；
> 6. 使用测试验证工作流的关键分支和安全不变量。

## 11.2 问题场景：从函数调用到状态图

> 第七章的最小链路可以用一段顺序代码表示，但完整系统存在很多分支：危险意图要提前结束，低置信意图要暂停澄清，Guard 拒绝不能进入 Repair，权限阻断不能执行，SQL 执行失败可以有限次修复。把这些分支全部写在一个 API 函数里，会很快变成难以测试的嵌套条件。
>
> LangGraph 将流程表示为有向图。节点负责一个职责，边负责连接，条件边负责根据状态选择下一步。图结构把“系统会如何走”显式化，也让测试可以针对某条边验证不可违反的安全规则。

## 11.3 AgentState：节点之间的共享协议

```python
class AgentState(TypedDict):
    question: str
    intent_is_safe: bool
    analysis_intent: Optional[Dict[str, Any]]
    grounding_result: Optional[Dict[str, Any]]
    schema_context: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    validated_sql: Optional[str]
    execution_success: bool
    retry_count: int
    answer: Optional[str]
```

> `AgentState` 是所有节点共享的数据协议。节点读取自己需要的字段，并返回要更新的字段；状态还保存审计事件、LLM 调用指标、认证用户和权限结果。
>
> 这里使用 `TypedDict` 而不是让每个节点传递不同的对象，是为了让图的边界稳定。类型标注帮助开发者阅读和静态检查，但运行时仍然需要在节点入口验证关键字典内容。

## 11.4 当前图的 12 个节点

| 顺序 | 节点 | 主要输入 | 主要输出 |
|---:|---|---|---|
| 1 | `check_intent` | 用户问题 | 安全结果和阻断原因 |
| 2 | `parse_intent` | 问题、上下文 | 结构化分析意图 |
| 3 | `ground_schema` | 分析意图 | 物理候选和路由 |
| 4 | `assess_clarification` | 意图、Grounding | 继续或澄清状态 |
| 5 | `load_schema` | 数据库连接 | 物理 Schema |
| 6 | `generate_sql` | 问题、上下文、Schema | 生成 SQL |
| 7 | `validate_sql` | 生成 SQL | 清理后的 SQL 或阻断 |
| 8 | `authorize_sql` | 清理后的 SQL、用户 | 权限结果和改写 SQL |
| 9 | `execute_sql` | 授权 SQL | 查询结果或执行错误 |
| 10 | `repair_sql` | SQL、错误、Schema | 修复后的 SQL |
| 11 | `optimize_sql` | 成功 SQL 和结果 | 优化建议 |
| 12 | `generate_answer` | 问题、SQL、结果 | 自然语言答案 |

> 这个顺序体现了“越早确定、越便宜的检查越靠前”：Intent Guard 在访问 Schema 和调用模型前执行，权限检查在真正执行前执行，答案生成只在结果成功后执行。

## 11.5 构建和编译 StateGraph

```python
workflow = StateGraph(AgentState)
workflow.add_node("check_intent", self._check_intent)
workflow.add_node("parse_intent", self._parse_intent)
workflow.add_node("execute_sql", self._execute_sql)
workflow.set_entry_point("check_intent")
return workflow.compile()
```

> `add_node()` 把节点名称和 Python 函数绑定，`set_entry_point()` 设置入口，`compile()` 生成可调用的图。节点名称是审计、追踪和调试的重要标识，不能随意使用含义不清的缩写。

## 11.6 普通边和条件边

### 11.6.1 普通边

```python
workflow.add_edge("parse_intent", "ground_schema")
workflow.add_edge("ground_schema", "assess_clarification")
workflow.add_edge("repair_sql", "validate_sql")
```

> 普通边表示无论节点结果如何都进入固定的下一个节点。`repair_sql → validate_sql` 特别重要：修复后的 SQL 不能直接执行，必须重新过安全校验。

### 11.6.2 条件边

```python
workflow.add_conditional_edges(
    "check_intent",
    self._should_load_schema,
    {"parse_intent": "parse_intent", "end": END},
)
```

> 条件函数读取状态并返回一个路由 key。Intent Guard 安全时返回 `parse_intent`，危险时返回 `end`。路由表明确列出每个结果去哪里，避免在函数里隐式跳转。

## 11.7 主路径和终止路径

```text
check_intent
  ├─ blocked → END
  └─ safe
      ↓
parse_intent → ground_schema → assess_clarification
                                      ├─ clarification_required → END
                                      └─ continue
                                          ↓
load_schema → generate_sql → validate_sql
                                  ├─ unsafe → END
                                  └─ safe → authorize_sql
                                                ├─ denied → END
                                                └─ allowed → execute_sql
                                                              ├─ success → optimize_sql → generate_answer → END
                                                              ├─ failed and retryable → repair_sql → validate_sql
                                                              └─ retries exhausted → END
```

> 图中的每条终止路径都对应一个安全或可靠性不变量：危险意图不调用下游依赖，澄清状态不消耗 SQL 生成，Guard 拒绝不进入 Repair，权限拒绝不执行，修复后不绕过 Guard。

## 11.8 节点如何返回状态增量

```python
return {
    "status": "completed" if result["is_safe"] else "blocked",
    "intent_is_safe": result["is_safe"],
    "intent_rule_id": result.get("rule_id"),
    "answer": answer,
    "audit_events": self._append_audit_event(...),
}
```

> 节点返回字典形式的状态增量，由 LangGraph 负责合并。项目中的审计辅助函数会基于旧列表创建新列表，避免直接原地修改共享状态。这种写法更适合测试，也降低异步节点之间互相覆盖数据的风险。

## 11.9 状态初始化与运行入口

> `AgentGraph.run()` 在图执行前构造完整初始状态，包括问题、会话 ID、历史上下文、默认重试计数、权限默认值和空审计列表。执行结束后构建审计报告，并根据状态决定是否保存澄清请求或追加会话摘要。

```python
final_state = await self.graph.ainvoke(initial_state)
final_state["audit_report"] = audit_report_builder.build_report(
    final_state,
    final_state.get("audit_events", []),
)
```

> 入口函数还可以接收 `on_progress` 回调，节点通过它向 SSE 层报告阶段和进度。进度回调是观察能力，不应该改变业务判定；回调异常会被吞掉，避免 UI 推送失败破坏查询主链路。

## 11.10 依赖注入与确定性测试

> `AgentGraph` 构造器允许注入 LLM Parser、SQL Generator、Answer Generator、Schema Loader、QueryRunner、Optimizer 和 SessionStore。生产默认使用全局实现，测试可以注入 Fake 或 Mock，从而在不调用真实模型的情况下运行完整图。

> 这不是“把真实逻辑替换掉就算测试完成”。核心路径测试仍然会运行真实的工作流、Guard、Grounding、权限和隔离数据库，只在外部模型边界注入确定性响应。这样可以把模型不稳定性与 Agent 编排正确性分开验证。

## 11.11 审计事件和可追踪性

> 每个重要节点都会追加审计事件，记录阶段、动作、状态、稳定消息、规则 ID 和必要细节。事件列表最终汇总到 `audit_report`，同时 LLM 观测模块记录调用阶段和耗时。

> 审计事件不是日志的替代品：日志用于开发诊断，审计报告用于请求级事实摘要。二者都不能保存 API Key、完整用户凭据或不必要的 SQL 字面量。

## 11.12 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/agents/state.py` | 定义共享状态 | 字段职责、默认值和类型 |
| `backend/app/agents/graph.py` | 构建和运行工作流 | 节点、边、条件和运行入口 |
| `backend/app/agents/audit.py` | 构建审计报告 | 事件和稳定摘要 |
| `backend/app/services/tracing.py` | 节点追踪装饰器 | 阶段标识和隐私边界 |
| `backend/tests/test_agent_graph.py` | 工作流行为测试 | 成功、阻断、修复和权限分支 |

## 11.13 动手验证

> 运行 AgentGraph 测试：

```bash
pytest backend/tests/test_agent_graph.py -q
```

> 重点观察测试中至少三种路径：成功查询会到达答案节点；Guard 拒绝不会调用 Repair；权限阻断不会执行或写入多轮上下文。测试名称和断言比单纯查看图结构更能说明系统行为。

## 11.14 常见错误

### 在节点中直接修改 `state`

> 原地修改可能让测试难以隔离，也会让多个节点共享不透明的副作用。优先返回状态增量，使用现有辅助函数合并审计列表。

### 把异常分支都连到 Repair

> Repair 只应该处理已经通过安全检查、但执行失败的 SQL。安全和权限拒绝必须走 END，否则可能产生绕过。

### 节点名称和审计名称不一致

> 这会让追踪、日志和评测报告无法对齐。新增节点时同步检查 `@trace_node`、审计事件和测试中的阶段名称。

### 让进度回调决定业务结果

> SSE 或日志只是观察通道；客户端断开时应该取消任务，但正常进度事件不能改变 SQL 安全或权限判定。

## 11.15 本章小结

> LangGraph 在本项目中的价值不是“让代码看起来像 Agent”，而是把状态、节点和分支显式化。图结构让安全终止、修复回流、审计和测试都有明确位置；`AgentState` 则把模块之间的输入输出固定下来。下一章会深入执行失败后的修复、SQL 优化和多轮会话状态。

## 11.16 练习

1. 从 `graph.py` 找出所有节点和条件边，画一张只包含安全分支的流程图。
2. 解释为什么 `repair_sql` 必须回到 `validate_sql`，而不是直接回到 `execute_sql`。
3. 在测试中找到权限阻断断言，说明它保护了哪些不可违反的行为。
4. 给一个节点增加新的状态字段时，列出需要同步修改的地方。
5. 说明为什么测试可以替换 LLM Client，但不能因此跳过 Guard 和权限节点。

## 11.17 下一章衔接

> 工作流已经能够在节点之间路由，但执行失败时还需要一种可控的恢复策略；用户追问时也需要保存足够但不过量的历史。下一章会把 Repair、Optimizer、ConversationContext 和 SQLite SessionStore 串起来。
