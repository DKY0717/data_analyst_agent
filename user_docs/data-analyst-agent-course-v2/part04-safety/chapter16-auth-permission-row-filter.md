# 第16章 认证、数据权限与行级过滤

> 本章预计 2 小时，学习“你是谁”与“你能查什么”的服务器端证据。实验使用测试凭据，不使用真实 Token。

## 16.1 学习目标

> 能区分认证、管理权限、角色策略、表/列授权、查询 scope、CTE/派生表解析和行级 SQL 改写；能解释 fail-closed policy。

## 16.2 前置知识

> 需要理解 FastAPI Depends、JWT/API Key、SQLGlot AST、CTE 与 JOIN。

## 16.3 为什么需要这一模块

> SQL Guard 判断语句是否危险，但不知道 analyst 是否能看 `customer_name` 或 `paid_amount`。认证提供 Principal，授权结合角色与实际 SQL 决定是否允许；前端显示的角色标签不具备安全效力。

## 16.4 输入、输出与依赖

| 阶段 | 输入 | 输出 |
|---|---|---|
| Authentication | Bearer JWT / API Key / disabled | AuthUser 摘要 |
| Policy loading | YAML 路径 | 经过校验的 RolePolicy |
| Authorization | user、validated SQL、Schema | allow/block、authorized_sql、事件 |

> AuthUser 只向 Agent 传 user_id、roles、auth_method 等摘要，不传原始 Token、Key 或请求头。

## 16.5 执行流程

```text
credential → verify signature/hash → AuthUser roles
  → parse SQL scopes/CTEs/physical sources
  → table policy → column policy → row filters
  → authorized SQL → QueryRunner
```

## 16.6 当前代码地图

| 内容 | 路径 |
|---|---|
| Auth | `backend/app/security/auth.py` |
| Policy model/loader | `backend/app/security/permission_policy.py` |
| Policy YAML | `backend/app/security/data_permissions.yaml` |
| Permission Guard | `backend/app/security/data_permission.py` |
| 集成测试 | `backend/tests/test_permission_execution_integration.py` |

## 16.7 关键代码理解

### 16.7.1 当前角色示例

> admin 可访问全部表列；analyst 能访问业务分析列，但客户姓名、支付金额、退款金额等敏感列受限，并对 orders 注入 region scope；support 只有地区、类别、商品、订单和明细表。该 YAML 是演示策略，不应未经评审直接当作企业权限模型。

### 16.7.2 API Key 只保存哈希映射

> 服务加载配置的 Key 并用哈希验证，避免在运行结构中到处传播明文。JWT 还要校验签名、有效期与角色；管理端点要求管理员或管理 API Key。

### 16.7.3 Scope-aware 列解析

> Permission Guard 不能把 CTE 名当物理表，也不能把派生表投影别名当底层敏感列。它借助 SQLGlot scope 追踪 physical source、star 展开与未限定列；歧义无法证明时阻断。

### 16.7.4 行过滤是确定性 AST 改写

> analyst 的 orders 查询会附加 `customer_id IN (...)` 区域约束，并生成 rule_id 与 `authorized_sql_changed` 证据。原 SQL 与授权 SQL必须区分，最终执行只能使用后者。

## 16.8 最小动手运行

> 工作目录：项目根目录。网络/真实模型：不需要。

```bash
pytest backend/tests/test_auth.py backend/tests/test_permission_policy.py backend/tests/test_data_permission_guard.py -q
```

## 16.9 故障注入实验

> 使用测试身份让 analyst 与 admin 查询客户姓名，预期前者命中列阻断、后者允许；再让 analyst 查询订单，确认授权 SQL增加行过滤。测试结束后清除临时环境变量。

## 16.10 调试路径与常见误判

> 401 查凭据，403/permission blocked 查角色和 policy，错误列归属查 SQL scope，结果范围异常查 authorized SQL 与 row_filters_applied。前端隐藏字段、Prompt 告诉模型“别查”和数据库用户权限都不能替代应用授权证据。

## 16.11 独立编码练习

> 为 support 角色写一份策略变更草案，明确允许表列、明确拒绝、是否有行过滤，以及 admin/analyst/support 三角色的允许与拒绝测试。不直接修改正式 YAML。

## 16.12 测试或评测验证

> 验证直接列、`*`、CTE、派生表、别名、COUNT(*)、歧义列、行过滤已有 WHERE 和实际执行结果；再运行离线 evaluator：

```bash
pytest backend/tests/test_permission_evaluator.py backend/tests/test_permission_execution_integration.py -q
```

## 16.13 面试复述题

> 1. Authentication 与 Authorization 有什么区别？
>
> 2. 为什么行级过滤不能交给 LLM？
>
> 3. CTE 和派生表为什么让列权限更难？

## 16.14 掌握度检查与下一章

> 能从 credential 追到 authorized SQL；能解释 scope-aware 解析；能用审计证明行过滤。下一章学习错误分类和失败隔离。
