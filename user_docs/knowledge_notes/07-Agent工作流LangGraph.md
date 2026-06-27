# Agent 工作流（LangGraph 核心）

## 1. 学习目标

> - 理解 LangGraph 的核心概念（StateGraph、节点、边、条件边）
> - 了解整个数据分析 pipeline 如何串联
> - 理解状态在节点之间如何传递
> - 看懂条件分支如何实现重试和终止逻辑

## 2. 什么是 LangGraph

> LangGraph 是 LangChain 生态中的工作流编排框架。它让你可以用"图"的方式定义 AI 应用的执行流程：
>
> - **节点（Node）**：一个处理步骤，比如"加载 Schema"、"生成 SQL"
> - **边（Edge）**：节点之间的连线，定义执行顺序
> - **条件边（Conditional Edge）**：根据条件决定下一步走哪条路
> - **状态（State）**：所有节点共享的数据字典
>
> 可以把它想象成一个流程图，每个方框是一个节点，箭头是边，菱形判断是条件边。

## 3. 状态定义

> 代码在 `backend/app/agents/state.py`。
>
> 所有节点通过一个共享的 `AgentState` 字典通信。每个节点读取需要的字段，写入产出的字段。

```python
from typing import TypedDict, Any, Optional, Dict, List

class AgentState(TypedDict):
    # 用户输入
    question: str                        # 用户的原始问题
    session_id: Optional[str]            # 多轮会话 ID

    # Intent Guard 结果
    intent_is_safe: bool                 # 是否通过安全检查
    intent_rule_id: Optional[str]        # 命中的规则 ID
    intent_category: Optional[str]       # 风险类别
    intent_error: Optional[str]          # 阻断原因

    # 意图解析结果
    analysis_intent: Optional[Dict]      # 结构化分析意图
    grounding_result: Optional[Dict]     # Schema Grounding 结果
    clarification_request: Optional[Dict] # 主动澄清请求

    # Schema 信息
    schema_context: Optional[Dict]       # 数据库表结构

    # SQL 处理
    generated_sql: Optional[str]         # LLM 生成的 SQL
    validated_sql: Optional[str]         # 校验后的 SQL（含 LIMIT）
    is_sql_safe: bool                    # SQL 是否安全
    validation_error: Optional[str]      # 校验失败原因

    # 执行结果
    execution_success: bool              # 执行是否成功
    query_result: Optional[Dict]         # 查询结果
    execution_error: Optional[str]       # 执行错误信息
    retry_count: int                     # 重试次数

    # 输出
    answer: Optional[str]                # 自然语言答案
    optimization_suggestions: List[str]  # 优化建议

    # 状态和审计
    status: str                          # 当前状态
    conversation_context: Optional[str]  # 多轮对话上下文
    audit_events: List[Dict]             # 审计事件
    audit_report: Optional[Dict]         # 审计报告
    llm_calls: List[Dict]               # LLM 调用指标
```

> **关键理解：** 状态是一个"大字典"，所有节点都在读写同一个字典。这比函数传参更灵活——节点不需要知道其他节点的签名，只需要读取状态中自己需要的字段。

## 4. 工作流图结构

> 代码在 `backend/app/agents/graph.py`。

### 4.1 节点注册

```python
workflow = StateGraph(AgentState)

# 注册 10 个节点
workflow.add_node("check_intent", self._check_intent)          # 安全检查
workflow.add_node("parse_intent", self._parse_intent)          # 意图解析
workflow.add_node("ground_schema", self._ground_schema)        # Schema Grounding
workflow.add_node("assess_clarification", ...)                 # 判断是否需要澄清
workflow.add_node("load_schema", self._load_schema)            # 加载 Schema
workflow.add_node("generate_sql", self._generate_sql)          # 生成 SQL
workflow.add_node("validate_sql", self._validate_sql)          # 校验 SQL
workflow.add_node("execute_sql", self._execute_sql)            # 执行 SQL
workflow.add_node("repair_sql", self._repair_sql)              # 修复 SQL
workflow.add_node("optimize_sql", self._optimize_sql)          # 优化建议
workflow.add_node("generate_answer", self._generate_answer)    # 生成答案
```

### 4.2 完整流程图

```text
                    ┌──────────────┐
                    │ check_intent │ ← 入口
                    └──────┬───────┘
                           │
                  ┌────────┴────────┐
                  │                 │
            (安全：放行)      (危险：阻断)
                  │                 │
                  ▼                 ▼
           ┌──────────────┐       END
           │  parse_intent │
           └──────┬───────┘
                  │
                  ▼
          ┌───────────────┐
          │ ground_schema  │
          └───────┬───────┘
                  │
                  ▼
        ┌──────────────────┐
        │assess_clarification│
        └────────┬─────────┘
                 │
        ┌────────┴────────┐
        │                 │
  (需要澄清)        (继续处理)
        │                 │
        ▼                 ▼
       END         ┌──────────────┐
                   │  load_schema  │
                   └──────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ generate_sql   │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ validate_sql   │
                  └───────┬───────┘
                          │
                 ┌────────┴────────┐
                 │                 │
           (SQL 安全)       (SQL 危险)
                 │                 │
                 ▼                 ▼
          ┌─────────────┐        END
          │ execute_sql  │
          └──────┬──────┘
                 │
        ┌────────┼────────┐
        │        │        │
    (成功)   (失败,可重试) (失败,重试耗尽)
        │        │        │
        ▼        ▼        ▼
  ┌──────────┐ ┌─────────┐ END
  │optimize_sql│ │repair_sql│
  └────┬─────┘ └────┬────┘
       │            │
       ▼            ▼
  ┌──────────────┐ validate_sql（回到校验）
  │generate_answer│
  └──────┬───────┘
         │
         ▼
        END
```

### 4.3 边的定义

```python
# 固定边：线性流程
workflow.add_edge("parse_intent", "ground_schema")
workflow.add_edge("ground_schema", "assess_clarification")
workflow.add_edge("load_schema", "generate_sql")
workflow.add_edge("generate_sql", "validate_sql")
workflow.add_edge("optimize_sql", "generate_answer")
workflow.add_edge("generate_answer", END)

# 条件边：根据状态决定下一步
workflow.add_conditional_edges(
    "check_intent",
    self._should_load_schema,
    {"parse_intent": "parse_intent", "end": END},
)

workflow.add_conditional_edges(
    "assess_clarification",
    self._should_continue_after_intent,
    {"load_schema": "load_schema", "end": END},
)

workflow.add_conditional_edges(
    "validate_sql",
    self._should_execute,
    {"execute": "execute_sql", "end": END},
)

workflow.add_conditional_edges(
    "execute_sql",
    self._should_continue,
    {"answer": "optimize_sql", "repair": "repair_sql", "end": END},
)

# 修复后必须再次校验
workflow.add_edge("repair_sql", "validate_sql")
```

## 5. 节点实现详解

### 5.1 check_intent（安全检查）

```python
async def _check_intent(self, state: AgentState) -> Dict[str, Any]:
    result = intent_guard.validate(state["question"])
    is_safe = bool(result["is_safe"])

    if not is_safe:
        return {
            "status": "blocked",
            "answer": f"请求已被安全策略阻断：{result.get('reason')}",
            ...
        }
    return {"status": "completed", "intent_is_safe": True, ...}
```

> 这是第一个节点，在调用任何 LLM 或数据库之前执行。如果被阻断，整个流程立即结束。

### 5.2 parse_intent（意图解析）

```python
async def _parse_intent(self, state: AgentState) -> Dict[str, Any]:
    question = state["question"]

    # 规则层：快速、确定性提取
    rule_intent = self.rule_parser.parse(question)

    # LLM 层：补充复杂场景
    llm_intent = await self.llm_parser.parse(question)

    # 合并：规则优先，LLM 补充
    merged = self.intent_merger.merge(rule_intent, llm_intent)

    return {"analysis_intent": merged.model_dump()}
```

> 意图解析采用"双层"策略：规则层快速提取明确信息（年份、Top-N），LLM 层补充隐式信息。

### 5.3 generate_sql（SQL 生成）

```python
async def _generate_sql(self, state: AgentState) -> Dict[str, Any]:
    output = await sql_generator.generate(
        state["question"],
        state["schema_context"],         # 表结构
        state.get("conversation_context"),  # 多轮上下文
        state.get("analysis_intent"),    # 意图解析结果
    )
    return {"generated_sql": output.sql}
```

### 5.4 validate_sql + execute_sql + repair_sql（校验-执行-修复循环）

> 这三个节点形成了一个**重试循环**：

```text
validate_sql → (安全) → execute_sql → (成功) → optimize_sql → generate_answer
                    ↓                       ↓
               (危险) END            (失败) → repair_sql → validate_sql（回到校验）
```

> **关键设计：修复后的 SQL 必须再次经过校验。**
>
> 这是为了防止 LLM 在修复过程中生成不安全的 SQL。比如原始 SQL 是安全的 SELECT，但执行失败后 LLM 可能在修复时"创造性地"生成了 INSERT 或 DELETE。

### 5.5 条件判断函数

```python
def _should_load_schema(self, state: AgentState) -> str:
    """安全则继续，否则终止"""
    return "parse_intent" if state["intent_is_safe"] else "end"

def _should_execute(self, state: AgentState) -> str:
    """SQL 安全则执行，否则终止"""
    return "execute" if state["is_sql_safe"] else "end"

def _should_continue(self, state: AgentState) -> str:
    """执行成功→生成答案，失败且可重试→修复，否则→终止"""
    if state["execution_success"]:
        return "answer"
    if state["retry_count"] < settings.SQL_MAX_RETRIES:
        return "repair"
    return "end"
```

## 6. 运行工作流

```python
async def run(self, question, session_id=None):
    # 初始化状态（所有字段设为默认值）
    initial_state: AgentState = {
        "question": question,
        "intent_is_safe": False,
        "retry_count": 0,
        "status": "completed",
        ...
    }

    # 运行图
    final_state = await self.graph.ainvoke(initial_state)

    # 构建审计报告
    final_state["audit_report"] = audit_report_builder.build_report(...)

    # 保存会话上下文（用于多轮对话）
    session_store.append_turn(session_id, final_state)

    return final_state
```

> `graph.ainvoke(initial_state)` 会按照图的定义，从入口节点开始，依次执行每个节点，直到到达 END。

## 7. 单例模式

```python
_agent_graph_instance: AgentGraph | None = None

def get_agent_graph() -> AgentGraph:
    """延迟初始化：首次调用时才创建"""
    global _agent_graph_instance
    if _agent_graph_instance is None:
        _agent_graph_instance = AgentGraph()
    return _agent_graph_instance
```

> 为什么延迟初始化？
>
> `AgentGraph` 的构造函数会初始化数据库连接和其他资源。如果在模块导入时就创建，可能导致循环依赖或启动时的性能问题。延迟初始化确保只在第一次请求时才创建。

## 8. 工作流设计总结

| 设计决策 | 原因 |
|----------|------|
| 使用 TypedDict 而非 Pydantic | LangGraph StateGraph 需要 TypedDict |
| 修复后重新校验 | 防止修复生成不安全 SQL |
| 重试上限 3 次 | 避免无限循环 |
| 延迟初始化 | 避免循环依赖和启动性能问题 |
| 审计事件贯穿全流程 | 方便安全审计和调试 |

## 9. 下一步

> Agent 工作流理解后，接下来学习：
>
> - **意图解析系统** — 了解规则解析器和 LLM 解析器如何协作
> - **SQL 生成、修复与优化** — 了解各节点的具体实现细节
