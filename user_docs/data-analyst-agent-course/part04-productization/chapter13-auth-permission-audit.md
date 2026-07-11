# 第十三章 身份认证、数据权限与安全审计

> 本章对应教学基线 `4d71b3c`。本章最后核对日期为 2026-07-11。

## 13.1 本章目标

> 完成本章后，你应该能够：
>
> 1. 区分 JWT、API Key、演示登录和未启用认证的边界；
> 2. 解释身份摘要为什么不能包含原始 Token；
> 3. 读懂 YAML 权限策略中的角色、表、字段和行过滤；
> 4. 理解 SQL Guard 之后为什么还要做数据权限检查；
> 5. 说明行级过滤如何在最终 SQL 执行前注入；
> 6. 理解审计报告如何记录允许、阻断和改写证据；
> 7. 使用权限测试验证越权 SQL 不执行也不进入修复。

## 13.2 问题场景：SQL 安全不等于数据授权

> 一条 SQL 可能完全符合 SELECT 语法，也没有读取文件或系统表，但它仍然可能暴露不应该给当前用户看的客户姓名、支付金额或其他敏感字段。
>
> SQL Guard 回答“这条语句是否允许执行”，Data Permission Guard 回答“当前身份是否能看到它引用的表和字段”。权限检查必须放在最终 SQL 确定之后、QueryRunner 执行之前，而且越权请求不能交给 Repair Agent 改写。

## 13.3 身份认证模型

### 13.3.1 JWT

> `create_jwt_token()` 使用 `JWT_SECRET` 和 HS256 签名，把用户 ID、角色、签发时间和过期时间放进 Token。`verify_jwt_token()` 验证签名和过期时间后才生成 `AuthUser`。

```json
{
  "sub": "demo:analyst",
  "roles": ["analyst"],
  "iat": 1720000000,
  "exp": 1720086400
}
```

> JWT 是身份声明，不是数据库权限本身。真正能访问哪些表和字段，还要由权限策略根据角色决定。

### 13.3.2 API Key

> API Key 适合后端到后端、CI 或监控脚本调用。代码只把 API Key 的 SHA-256 哈希放进内存映射，并在身份摘要中保留截断标识，不保存完整 Key。API Key 默认会被归一为 analyst 角色，具体权限仍由 YAML 策略决定。

### 13.3.3 本地免认证和演示登录

> 当没有配置 `JWT_SECRET` 和 `API_KEYS` 时，`get_current_user()` 返回 `None`，这是本地开发放行模式。启用 `AUTH_DEMO_ENABLED=true` 后，前端可以用 `admin`、`analyst` 和 `support` 演示角色获取本地 Token。
>
> 免认证模式适合开发，不应被描述成生产安全配置。生产或 secure profile 应配置足够长度的 Secret/API Key，并关闭演示登录入口。

## 13.4 FastAPI 认证依赖

```python
async def get_current_user(request: Request, credentials=None):
    if not is_auth_enabled():
        return None

    if credentials and credentials.credentials:
        token = credentials.credentials
        if token.startswith("eyJ"):
            return verify_jwt_token(token)
        return verify_api_key(token)

    api_key = request.headers.get("X-API-Key")
    if api_key:
        return verify_api_key(api_key)

    raise HTTPException(status_code=401, detail="缺少认证凭证")
```

> 认证依赖只负责识别身份并返回最小的 `AuthUser`。它不读取 SQL、不解析 Schema，也不把原始 Authorization 头传入 AgentState。这样权限模块只需要 `user_id`、`auth_method` 和角色列表。

## 13.5 YAML 权限策略

> `backend/app/security/data_permissions.yaml` 把权限从 Python 代码中外置，使策略可以审阅、版本化和单独测试。策略包含版本号、角色、表、字段列表和可选行级过滤。

```yaml
version: 1
roles:
  analyst:
    tables:
      orders:
        columns:
          - order_id
          - order_date
          - total_amount
        row_filter:
          expression: "customer_id IN (SELECT customer_id FROM customers WHERE region_id IN (1, 2))"
          rule_id: row_filter_region_scope
```

> 策略加载器会校验 YAML 结构、版本号、角色名、表名、列名和行过滤表达式。行过滤表达式本身也会通过 SQLGlot 解析，避免配置文件成为未经检查的 SQL 注入入口。

## 13.6 表级与字段级授权

> Data Permission Guard 先从最终 SQL AST 提取引用表和列，再把角色权限合并成允许集合。多个角色取权限并集，未知角色不会获得隐式权限；表级拒绝优先于字段级检查。

```text
SQL 引用表/字段
  ↓
加载角色策略
  ↓
表是否允许？→ 否：block_unauthorized_table
  ↓ 是
字段是否允许？→ 否：block_unauthorized_column
  ↓ 是
继续行级过滤和执行
```

> `*` 可以表示所有表或所有字段，但不应该被误解为“忽略所有安全规则”。策略加载器仍然会验证配置格式，审计报告仍然记录授权结果。

## 13.7 行级过滤

### 13.7.1 为什么要改写 SQL

> 表和列权限只能回答“能看到哪些结构”，不能回答“能看到哪几行”。例如 analyst 可以查看订单销售额，但只允许看到指定区域。Data Permission Guard 会在执行前将行过滤表达式注入最终 SQL，并把命中的规则 ID 写入审计摘要。

```text
原 SQL:
SELECT SUM(o.total_amount) FROM orders o

授权 SQL:
SELECT SUM(o.total_amount)
FROM orders o
WHERE o.customer_id IN (
  SELECT customer_id FROM customers WHERE region_id IN (1, 2)
)
```

> 真实注入位置由 SQL AST 和表别名决定，不能用简单字符串拼接。自连接、子查询和 CTE 需要分别处理作用域，否则过滤条件可能绑错表或被绕过。

### 13.7.2 改写后再次校验

> 权限改写得到 `authorized_sql` 后，完整工作流会继续使用它执行；安全测试还会验证改写后的 SQL 可以重新通过 SQL Guard 并在隔离 DuckDB 中返回授权区域。改写本身不能跳过 SQL 安全层。

## 13.8 审计报告

> `audit_report_builder` 将身份摘要、最终 SQL 安全状态、执行成功、重试次数、LIMIT 改写、阻断规则、权限可观测性、LLM 观测和事件明细汇总到 `AuditReport`。

| 字段 | 说明 | 不应包含 |
|---|---|---|
| `user_id` | 当前用户 ID | Token 原文 |
| `auth_method` | jwt、api_key 或 disabled | Authorization 头 |
| `roles` | 角色摘要 | 完整策略文件 |
| `blocked_rules` | 稳定规则 ID | 敏感问题原文 |
| `permission_observability` | 检查、允许、引用表列、行过滤 | 完整策略表达式 |
| `events` | 每阶段稳定事件 | 不必要的数据库异常原文 |

> 审计报告的目标是让开发者和面试演示能够回答“为什么允许/阻断”，不是把所有内部数据复制到前端。稳定规则 ID 比一段可能泄露数据的长错误更适合回归测试。

## 13.9 权限阻断的工作流边界

```text
SQL Guard 通过
  ↓
Data Permission Guard
  ├─ 不允许 → 返回 blocked，不执行，不 Repair，不写会话
  └─ 允许 → 执行授权后的 SQL
```

> 权限阻断不进入 SQL Repair，是一个必须测试的不变量。如果让模型修复越权 SQL，它可能通过换别名、换表或改写字段继续尝试访问同一敏感数据。

## 13.10 代码地图

| 文件 | 作用 | 阅读重点 |
|---|---|---|
| `backend/app/security/auth.py` | JWT、API Key 与 FastAPI 依赖 | 身份验证、失效和最小摘要 |
| `backend/app/security/permission_policy.py` | YAML 策略加载和校验 | 版本、角色、行过滤 AST |
| `backend/app/security/data_permissions.yaml` | 当前角色策略 | admin、analyst、support |
| `backend/app/security/data_permission.py` | 表列授权和行级改写 | AST、别名、拒绝路径 |
| `backend/app/agents/audit.py` | 构建审计报告 | 事件、阻断规则和隐私 |
| `backend/tests/test_auth.py` | 认证测试 | Token、API Key、免认证 |
| `backend/tests/test_data_permission_guard.py` | 权限测试 | 表列权限、行过滤和拒绝 |

## 13.11 动手验证

> 运行确定性权限和认证测试：

```bash
pytest backend/tests/test_auth.py backend/tests/test_data_permission_guard.py -q
```

> 如果本地开启演示登录，可以执行：

```bash
python scripts/interview_demo_preflight.py --strict
```

> 预检只报告 Secret 是否存在，不输出 Secret 值。演示时可以先用 analyst 查询销售额，再用 analyst 查询客户姓名，观察前者允许、后者被 `block_unauthorized_column` 阻断；切换 admin 后再比较结果。

## 13.12 常见错误

### 只在前端隐藏字段

> 前端隐藏不是权限控制。用户可以直接构造 HTTP 请求，因此表列和行权限必须在后端最终 SQL 上确定性执行。

### 用用户输入拼接行过滤

> 行过滤应该来自已校验的 YAML 策略和 AST 改写，不能把用户问题或自由文本直接拼入 WHERE 子句。

### 认证成功就默认拥有全部权限

> 身份验证和授权是两个阶段。JWT 只证明 Token 有效，角色策略才决定能访问什么。

### 权限失败仍写入多轮上下文

> 这样下一轮模型可能继承越权字段或表名。权限阻断必须在 `SessionStore.append_turn()` 之前终止。

## 13.13 本章小结

> 认证确定“你是谁”，策略确定“你能看什么”，权限 Guard 确定“这条最终 SQL 是否越权”，审计报告解释“系统为什么放行或阻断”。这条链路必须位于 QueryRunner 之前，并且越权 SQL 不得被修复或进入会话上下文。

## 13.14 练习

1. 画出 JWT 解析到 Data Permission Guard 的数据流，标出 Token 在哪里被截断为身份摘要。
2. 在 YAML 中找到 analyst 的行过滤规则，说明它作用于哪个业务场景。
3. 构造一个字段允许但表不允许的请求，判断哪一条规则先命中。
4. 说明为什么权限改写后仍需经过 SQL Guard。
5. 阅读审计报告模型，找出三个不应保存敏感原文的字段。

## 13.15 下一章衔接

> 后端现在具备身份、权限和审计能力，但一次查询可能需要较长时间，用户也需要实时看到阶段进度。下一章会学习 SSE、缓存、追踪、LLM 成本观测和 A/B Prompt 记录。
