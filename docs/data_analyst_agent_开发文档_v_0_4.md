# Data Analyst Agent 开发文档 v0.4

## 1. 版本目标

v0.4 在现有 NL2SQL、SQL Guard、自动修复和评测体系之上增加 Intent Guard，使明确危险请求在 Schema 加载、Qwen 调用和数据库访问之前终止。

本版本解决的核心问题是：只校验 LLM 生成的 SQL 仍然太晚，危险意图可能被模型改写成无害 SQL，导致系统无法稳定证明“危险请求已被安全策略识别并阻断”。

## 2. 三层安全治理

```text
用户问题
  -> Intent Guard：识别明确危险自然语言意图
  -> SQL Guard：使用 SQLGlot AST 校验生成 SQL
  -> Execution Guard：只执行已通过校验的 SQL，并限制结果规模
```

- Intent Guard 处理用户意图，危险请求不消耗 Qwen Token，也不读取 Schema。
- SQL Guard 处理模型输出，阻断 DDL/DML、多语句、系统表和危险函数。
- Execution Guard 负责只读执行、LIMIT、错误结构化和修复后重新校验。

## 3. Intent Guard 设计

Intent Guard 使用确定性“危险动作 + 危险目标”组合规则，不调用 LLM、不访问数据库。当前覆盖五类高置信危险意图：

| 类别 | 规则 ID | 示例 |
|---|---|---|
| 数据修改/删除 | `block_destructive_intent` | 删除所有订单 |
| 凭据访问 | `block_credential_access_intent` | 查看 API token |
| 系统资源访问 | `block_system_access_intent` | 读取 `/etc/passwd` |
| 安全控制绕过 | `block_security_bypass_intent` | 绕过 SQL Guard |
| 批量敏感数据导出 | `block_sensitive_export_intent` | 导出全部客户手机号 |

设计原则：

1. 高置信阻断，模糊请求放行给后续 SQL Guard。
2. 逐逻辑片段匹配，避免跨子句拼接动作和目标造成误杀。
3. 支持中文、英文、复合命令和软标点表达。
4. 识别否定、防护、被动分析语境，降低误杀。
5. 返回固定规则元数据，不回显凭据或匹配片段。
6. Guard 异常时 fail-closed，使用稳定规则 `block_intent_guard_error`。

## 4. LangGraph 流程变化

`check_intent` 是唯一入口节点：

```text
check_intent
  ├─ blocked -> END
  └─ safe -> load_schema -> generate_sql -> validate_sql -> execute_sql ...
```

阻断状态包含 `intent_is_safe`、`intent_rule_id`、`intent_category` 和 `intent_error`。阻断请求的 SQL 为空字符串、LLM 调用列表为空，并生成 `stage=intent` 的审计事件。AgentGraph 仍统一调用 SessionStore，但 SessionStore 会拒绝保存 Intent Guard 阻断轮次。

## 5. API 契约

危险请求属于正常安全决策，不使用异常表达，因此 `/api/chat/query` 仍返回 HTTP 200：

- `intent_is_safe=false`
- `intent_rule_id` 和 `intent_category` 可直接展示
- `sql=""`、`columns=[]`、`rows=[]`
- `answer` 给出稳定阻断原因
- `audit_report.blocked_rules` 保存规则证据

API 和 Agent 日志不记录原始危险问题；内部异常也不向客户端回显。

## 6. 独立危险意图评测

新增 37 条固定 case，不依赖 Qwen 或数据库：

| 指标 | v0.4 基线 |
|---|---:|
| 危险意图阻断率 | 100% |
| 安全意图通过率 | 100% |
| 误杀率 | 0% |
| 预期规则匹配率 | 100% |

分类包含 25 条危险请求和 12 条安全分析对照。评测同时输出中文 Markdown 和 JSON，并使用退出码 `0/1/2` 区分达标、质量失败和输入错误。

## 7. NL2SQL 分层阻断指标

NL2SQL 评测新增：

- `intent_is_safe`
- `intent_blocked`
- `intent_rule_id`
- `blocked_stage`
- `unsafe_intent_block_rate`
- `unsafe_sql_block_rate`

2026-06-11 Qwen Plus 真实基线：

| 指标 | 结果 |
|---|---:|
| 正常分析执行成功率 | 24/24，100% |
| 危险请求总体阻断率 | 8/8，100% |
| Intent Guard 提前阻断率 | 4/8，50% |
| SQL Guard 阻断率 | 4/8，50% |
| 安全预期命中率 | 32/32，100% |
| SQL Repair 端到端成功率 | 6/6，100% |

## 8. CI 与质量门禁

- 普通 CI 运行后端测试、前端构建、Secret Scan 和确定性 Intent Evaluation，不使用 Qwen Secret。
- 手动真实 Qwen workflow 运行 Intent、NL2SQL、SQL Repair 和强制质量门禁，并上传全部报告。
- 质量门禁要求正常分析执行率、危险请求阻断率、安全预期命中率和 Repair 端到端成功率全部为 100%。

## 9. 验收结果

- 后端：`216 passed`
- 前端：Vite production build 成功
- Secret Scan：通过
- 确定性 Intent Evaluation：四项指标全部达标
- 真实 Qwen Plus NL2SQL：质量门禁通过
- 真实 Qwen Plus SQL Repair：6/6

## 10. 当前边界与后续路线

Intent Guard 是高置信规则引擎，不试图理解任意自然语言攻击表达。模糊请求仍交给 SQL Guard 和执行控制处理。下一阶段可继续建设：

1. Tool Registry：为 Agent 工具声明权限、输入输出和审计策略。
2. Schema Context Manager：按问题选择相关 Schema，降低 Token 和延迟。
3. Audit Timeline：把 Intent、SQL、执行和 LLM 指标持久化为可检索时间线。
