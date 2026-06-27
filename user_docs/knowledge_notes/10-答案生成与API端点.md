# 答案生成与 API 端点

## 1. 学习目标

> - 了解答案生成器如何将查询结果转换为自然语言
> - 理解 API 端点如何组装和返回完整结果
> - 了解多轮对话和会话管理的实现

## 2. 答案生成器

> 代码在 `backend/app/agents/answer_generator.py`。
>
> 答案生成器是 pipeline 的最后一步，把技术性的 SQL 结果转换为用户易懂的自然语言。

### 2.1 输入信息

> 答案生成需要三个输入：

| 输入 | 说明 |
|------|------|
| 用户原始问题 | 理解用户想知道什么 |
| 执行的 SQL | 理解查询逻辑 |
| 查询结果 | 包含 columns 和 rows |

### 2.2 Prompt 设计

```python
system_prompt = """你是一个数据分析助手。

要求：
1. 用通俗易懂的语言解释查询结果
2. 突出关键数据和趋势
3. 如果结果为空，说明可能的原因
4. 不要重复 SQL 语句本身"""
```

> **为什么不让 LLM 重复 SQL？**
>
> 用户不关心 SQL 细节，他们只想知道结果意味着什么。比如用户问"销售额最高的商品是什么"，他们期望的回答是"销售额最高的商品是 Laptop，销售额为 ¥123,456"，而不是一串 SQL 代码。

### 2.3 结果格式化

> 查询结果需要格式化为 LLM 能理解的文本：

```python
def _format_query_result(self, query_result: dict) -> str:
    if not query_result.get("rows"):
        return "查询结果为空"

    columns = query_result["columns"]
    rows = query_result["rows"]

    lines = []
    lines.append("列名: " + ", ".join(columns))
    lines.append(f"共 {len(rows)} 条记录")

    # 最多显示前 10 条
    for i, row in enumerate(rows[:10]):
        lines.append(f"记录 {i + 1}: {row}")

    if len(rows) > 10:
        lines.append(f"... 还有 {len(rows) - 10} 条记录")

    return "\n".join(lines)
```

> 限制显示 10 条记录是为了控制 prompt 长度，避免超出 LLM 的上下文窗口。

## 3. API 端点详解

### 3.1 核心查询端点

> 代码在 `backend/app/api/query.py`。

```python
@router.post("/api/chat/query", response_model=SuccessResponse)
async def query(request: QueryRequest):
    # 1. 运行 Agent 工作流
    result = await get_agent_graph().run(
        request.question,
        session_id=request.session_id,
    )

    # 2. 构建响应
    response = QueryResponse(
        question=result["question"],
        session_id=result.get("session_id"),
        status=result.get("status", "completed"),
        sql=result.get("validated_sql") or result.get("generated_sql") or "",
        columns=query_result.get("columns", []),
        rows=query_result.get("rows", []),
        answer=result.get("answer") or "抱歉，处理您的问题时遇到困难。",
        execution_time_ms=query_result.get("execution_time_ms", 0),
        retry_count=result.get("retry_count", 0),
        optimization_suggestions=result.get("optimization_suggestions", []),
        analysis_intent=result.get("analysis_intent"),
        clarification=result.get("clarification_request"),
        audit_report=result.get("audit_report"),
    )

    return SuccessResponse(code=200, message="success", data=response)
```

### 3.2 响应结构

> 一个完整的查询响应包含以下信息：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "question": "销售额最高的前5个商品",
    "session_id": "abc123",
    "status": "completed",
    "intent_is_safe": true,
    "sql": "SELECT p.product_name, SUM(oi.quantity * oi.unit_price) AS sales FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.product_name ORDER BY sales DESC LIMIT 5",
    "is_sql_safe": true,
    "columns": ["product_name", "sales"],
    "rows": [
      ["Laptop", 123456.00],
      ["Smartphone", 98765.00],
      ["Tablet", 45678.00],
      ["Smartwatch", 23456.00],
      ["Headphones", 12345.00]
    ],
    "answer": "销售额最高的前5个商品分别是：Laptop（¥123,456）、Smartphone（¥98,765）、Tablet（¥45,678）、Smartwatch（¥23,456）和 Headphones（¥12,345）。其中 Laptop 的销售额遥遥领先。",
    "execution_time_ms": 15,
    "retry_count": 0,
    "optimization_suggestions": [],
    "audit_report": {
      "is_sql_safe": true,
      "execution_success": true,
      "events": [...]
    }
  }
}
```

### 3.3 状态类型

> `status` 字段表示请求的处理状态：

| 状态 | 说明 |
|------|------|
| `completed` | 正常完成，有查询结果和答案 |
| `blocked` | 被 Intent Guard 或 SQL Guard 阻断 |
| `clarification_required` | 需要用户澄清问题 |
| `clarification_expired` | 澄清请求已过期 |

## 4. 多轮对话管理

> 代码在 `backend/app/agents/session_store.py`。
>
> 系统支持多轮对话，用户可以追问。比如：
>
> - 第一轮："各地区的销售额是多少"
> - 第二轮："华东地区再按月拆分一下"
> - 第三轮："换成利润率看看"

### 4.1 会话存储

```python
class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, List[dict]] = {}

    def get_context(self, session_id: str) -> str:
        """获取会话的历史上下文摘要"""
        turns = self._sessions.get(session_id, [])
        if not turns:
            return ""

        # 构建上下文摘要
        context_parts = []
        for turn in turns[-3:]:  # 最近 3 轮
            context_parts.append(f"问题: {turn['question']}")
            context_parts.append(f"SQL: {turn['sql']}")
        return "\n".join(context_parts)

    def append_turn(self, session_id: str, state: AgentState):
        """保存本轮对话结果"""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append({
            "question": state["question"],
            "sql": state.get("validated_sql"),
            "answer": state.get("answer"),
        })
```

> **上下文继承机制：**
>
> 当用户追问"华东地区再按月拆分一下"时，系统会把前几轮的"问题 + SQL"注入到 prompt 中，让 LLM 理解"拆分"是指对上一轮的 SQL 按月维度拆分。

### 4.2 主动澄清

> 当用户的问题太模糊时，系统会暂停并返回澄清请求：

```python
# 用户: "分析一下"
# 系统返回:
{
  "status": "clarification_required",
  "clarification": {
    "clarification_id": "uuid",
    "reason": "指标缺失",
    "question": "您想分析什么指标？比如销售额、订单数、利润等？",
    "candidates": [
      {"id": "sales_amount", "label": "销售额"},
      {"id": "order_count", "label": "订单数"},
      {"id": "profit", "label": "利润"}
    ]
  }
}
```

> 用户选择候选或输入自由文本后，系统恢复执行。

## 5. 安全审计报告

> 每次查询都会生成一份审计报告，记录安全相关的事件：

```python
class AuditReport(BaseModel):
    question: str                    # 用户问题
    final_sql: str                   # 最终执行的 SQL
    is_sql_safe: bool                # SQL 是否安全
    execution_success: bool          # 是否执行成功
    retry_count: int                 # 重试次数
    limit_injected: bool             # 是否注入了 LIMIT
    blocked_rules: List[str]         # 命中的阻断规则
    llm_observability: LLMObservability  # LLM 调用指标
    events: List[AuditEvent]         # 审计事件明细
```

> 审计报告记录了从 Intent Guard 到最终答案生成的每一步安全决策，方便安全审计和问题排查。

## 6. 下一步

> 后端所有模块理解后，接下来学习：
>
> - **前端开发（Vue 3）** — 了解界面如何实现
