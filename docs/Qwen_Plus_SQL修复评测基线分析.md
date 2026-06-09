# Qwen Plus SQL 修复评测基线分析

## 1. 评测目标

普通 NL2SQL 评测主要验证“从问题生成 SQL”的整体效果，但很难稳定触发某一种执行错误。为了单独证明 SQL Repair Agent 的能力，本项目新增了独立故障注入评测器：

```text
固定安全错误 SQL
  -> SQL Guard
  -> DuckDB 确认执行失败
  -> Qwen Plus Repair
  -> 修复后再次通过 SQL Guard
  -> DuckDB 执行
  -> 规则化意图保持检查
```

该评测不修改正常 AgentGraph，也不把危险 SQL 交给 Repair。每条原始 SQL 都必须先通过 Guard，并且必须在真实 DuckDB 中稳定失败，才能进入修复阶段。

运行命令：

```bash
cd backend
python -m evaluation.repair_evaluator
```

## 2. 固定故障集

当前包含 6 类确定性故障：

| Case | 故障类型 |
|---|---|
| `wrong_order_amount_column` | 引用不存在的销售额字段 |
| `wrong_order_items_table` | 引用不存在的订单明细表 |
| `missing_customer_join` | 查询客户名称时缺少关联 |
| `mysql_date_format` | 使用 MySQL 日期格式函数 |
| `unsupported_quarter_format` | 使用 DuckDB 不支持的季度格式符 |
| `wrong_region_column` | 引用不存在的地区字段 |

## 3. 第一轮真实基线

使用本地配置的 `qwen-plus` 运行 6 条用例，结果如下：

| 指标 | 结果 |
|---|---:|
| 故障注入成功率 | 6/6，100% |
| Repair 输出成功率 | 6/6，100% |
| 修复后 Guard 通过率 | 6/6，100% |
| 修复后执行成功率 | 5/6，83.3% |
| 意图保持率 | 6/6，100% |
| 端到端修复成功率 | 5/6，83.3% |

失败用例为 `unsupported_quarter_format`。模型识别出 `%q` 不受 DuckDB 支持，但生成了类似下面的表达式：

```sql
CAST((strftime('%m', order_date) - 1) / 3 + 1 AS INTEGER)
```

根因是 `strftime` 返回字符串，字符串在参与减法前没有显式转换为数值，因此 DuckDB Binder 拒绝执行。

第一轮报告：

- `backend/evaluation/reports/sql-repair-evaluation-2026-06-09-203755.md`
- `backend/evaluation/reports/sql-repair-evaluation-2026-06-09-203755.json`

## 4. 最小改进

针对真实失败原因，先新增单元测试固定 Repair prompt 的 DuckDB 约束，再补充两条明确规则：

1. 季度提取优先使用 `EXTRACT(QUARTER FROM date_column)`，不要使用不受支持的 `%q/%Q`。
2. `strftime` 等函数返回字符串；字符串参与算术前必须显式 `CAST` 为数值类型。

这次改动只增强 Repair Agent 的方言提示，不针对评测 case 硬编码 SQL，也不修改正常 AgentGraph 路由。

## 5. 第二轮真实基线

相同 6 条用例使用 `qwen-plus` 重跑后：

| 指标 | 结果 |
|---|---:|
| 故障注入成功率 | 6/6，100% |
| Repair 输出成功率 | 6/6，100% |
| 修复后 Guard 通过率 | 6/6，100% |
| 修复后执行成功率 | 6/6，100% |
| 意图保持率 | 6/6，100% |
| 端到端修复成功率 | 6/6，100% |

季度用例被修复为：

```sql
SELECT EXTRACT(QUARTER FROM order_date) AS quarter,
       SUM(total_amount) AS sales_amount
FROM orders
GROUP BY quarter
```

第二轮报告：

- `backend/evaluation/reports/sql-repair-evaluation-2026-06-09-204019.md`
- `backend/evaluation/reports/sql-repair-evaluation-2026-06-09-204019.json`

## 6. 如何向面试官解释

这套评测的价值不是展示一次“模型答对了”，而是建立可重复的工程闭环：

1. 用确定性故障隔离 Repair 能力，避免依赖模型是否碰巧生成错误 SQL。
2. 同时验证数据库失败、Repair 输出、Guard、安全执行和意图保持。
3. 保留改进前后的真实报告，用失败样本驱动 prompt 约束和回归测试。
4. Repair 只处理通过 Guard 的安全查询，危险请求不会被模型“修复”后执行。

## 7. 当前边界

- 当前只有 6 类故障，覆盖常见字段、表、JOIN 和方言问题，但还不是完整错误分类体系。
- 意图保持检查是规则化检查，能验证关键表、列和结果形状，不能完全替代人工业务语义判断。
- 真实 LLM 输出存在随机性，100% 是本次基线结果，不代表所有运行都必然相同。
- 后续可增加超时、复杂聚合、窗口函数和多表歧义等 Repair case，并记录 token、延迟和调用成本。
