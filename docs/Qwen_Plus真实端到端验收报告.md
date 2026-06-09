# Qwen Plus 真实端到端验收报告

## 1. 验收目标

验证项目在真实 DashScope `qwen-plus` 模型下，能够完整贯通以下能力：

1. 自然语言生成 DuckDB SQL。
2. SQL Guard 安全校验与自动 LIMIT。
3. DuckDB 查询执行。
4. SQL 优化建议生成。
5. 自然语言答案生成。
6. API 多轮会话上下文继承。
7. 业务语义层指标口径应用。
8. 全链路安全审计报告生成。

## 2. 验收环境

- 验收日期：2026-06-09
- LLM 模型：`qwen-plus`
- LLM 服务：阿里云 DashScope
- 数据库：DuckDB
- 数据表数量：8
- 后端单元测试：95 项

API Key 仅通过本地 `.env` 加载，未写入报告或 Git。

## 3. 验收结果

### 3.1 单轮商品销售额分析

用户问题：

> 统计销售额最高的前 5 个商品

生成并执行的 SQL：

```sql
SELECT
  p.product_name,
  SUM(oi.quantity * oi.unit_price) AS sales_amount
FROM order_items AS oi
JOIN products AS p ON oi.product_id = p.product_id
GROUP BY p.product_name
ORDER BY sales_amount DESC
LIMIT 5
```

结果：

- SQL 安全校验通过。
- SQL 执行成功，返回 5 行。
- 修复重试次数为 0。
- 成功生成自然语言分析答案。
- 成功生成 6 条审计事件。

### 3.2 API 多轮追问

同一 `session_id` 下连续提问：

1. `统计各地区的销售额并从高到低排序`
2. `只看前三名`

第二轮生成并执行的 SQL：

```sql
SELECT
  r.region_name,
  SUM(o.total_amount) AS 销售额
FROM orders AS o
JOIN customers AS c ON o.customer_id = c.customer_id
JOIN regions AS r ON c.region_id = r.region_id
GROUP BY r.region_name
ORDER BY 销售额 DESC
LIMIT 3
```

结果：

- 两次 API 请求均返回 HTTP 200。
- 两轮请求正确复用同一会话 ID。
- 第二轮成功继承上一轮的销售额指标、地区维度、JOIN 关系和排序规则。
- 第二轮将模糊追问“只看前三名”正确转换为 `LIMIT 3`。
- 第二轮返回 3 行，SQL 安全校验通过，修复重试次数为 0。

### 3.3 业务语义层退款率分析

用户问题：

> 统计各商品类别的退款率，按退款率从高到低排序

生成并执行的 SQL：

```sql
SELECT
  c.category_name,
  COUNT(DISTINCT r.refund_id) * 1.0
    / NULLIF(COUNT(DISTINCT o.order_id), 0) AS refund_rate
FROM orders AS o
JOIN order_items AS oi ON o.order_id = oi.order_id
JOIN products AS p ON oi.product_id = p.product_id
JOIN categories AS c ON p.category_id = c.category_id
LEFT JOIN refunds AS r ON o.order_id = r.order_id
GROUP BY c.category_name
ORDER BY refund_rate DESC
LIMIT 1000
```

结果：

- 正确使用退款订单数除以订单数的退款率口径。
- 正确使用 `NULLIF` 防止除零。
- 正确使用 `LEFT JOIN refunds`，避免丢失没有退款的订单。
- SQL 安全校验通过，执行成功，返回 8 个商品类别。
- 生成顺序扫描相关优化建议。
- 生成包含 Schema、生成、Guard、执行、优化和答案阶段的完整审计报告。

## 4. 验收结论

当前 v0.3 已在真实 `qwen-plus` 环境下通过核心端到端验收。

项目不再只是一个“调用大模型生成 SQL”的演示，而是具备以下可用于技术面试展开的工程能力：

- 通过 SQL Guard 控制大模型生成 SQL 的执行边界。
- 通过语义层约束业务指标口径与 JOIN 关系。
- 通过多轮会话支持省略指标和维度的连续追问。
- 通过优化器和审计报告增强可解释性。
- 通过固定测试集和真实端到端验收共同证明系统质量。

## 5. 后续建议

1. 在 CI 中加入不依赖真实 API 的 95 项单元测试。
2. 增加可选的真实 Qwen 冒烟测试，由手动或定时任务触发。
3. 对 32 条 NL2SQL 评测集运行真实模型，形成基线成功率报告。
4. 为 LLM 调用增加 token、耗时和费用统计。
5. 增加 Redis 会话存储与会话过期策略。
