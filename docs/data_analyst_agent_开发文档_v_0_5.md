# Data Analyst Agent 开发文档 v0.5

## 1. 版本目标

v0.5 建立结果正确性黄金基准，回答一个比“SQL 是否执行成功”更严格的问题：

> Agent 返回的列结构、结果值、排序和核心业务指标，是否真的与人工审核口径一致？

SQL 能执行只说明语法和字段有效。错误 JOIN、错误聚合粒度、错误业务口径和不稳定输出别名仍可能生成看似合理、实际错误的分析结果。

## 2. 黄金 Case

第一版包含 10 条人工审核问题，覆盖：

- 时间序列：月销售额、月订单数。
- Top N：销售额最高的 5 个商品。
- 维度拆分：地区、商品类别、支付方式。
- 核心业务指标：退款率、客单价、复购率。

每条 case 定义参考 SQL、比较模式、标准列、数值容差和可选固定断言。参考 SQL 必须经过现有 SQL Guard 后才能执行。

## 3. 比较策略

`ResultComparator` 支持四种确定性模式：

| 模式 | 用途 |
|---|---|
| `unordered` | 忽略行顺序，保留重复行数量 |
| `ordered` | 结果值与行顺序都必须一致 |
| `top_n` | Top N 行数、值和顺序必须一致 |
| `scalar` | 必须返回唯一标量结果 |

数值使用绝对容差比较。固定断言支持行数、列求和和标量值，用于锁定种子库中的稳定业务事实。比较器不访问数据库、不调用 Qwen；真实比较无损，报告差异样本最多保留五条。

## 4. 评测链路

```text
黄金问题
  -> AgentGraph / Qwen 生成并执行 SQL
  -> ReferenceQueryRunner
       -> SQL Guard
       -> 固定 DuckDB 参考 SQL
  -> ResultComparator
  -> ResultCorrectnessEvaluator
  -> CorrectnessReportWriter
```

单条 Agent、参考查询或比较异常会转换为稳定失败类型，不会中断整批评测。评测结果只保存 Agent SQL、指标和有限差异，不保存完整大结果集。

## 5. 正确性指标

- 结果正确率
- 列结构匹配率
- 结果值匹配率
- 排序匹配率
- 核心业务指标命中率
- 参考 SQL Guard 通过率
- 参考 SQL 执行成功率
- 固定断言通过率

## 6. 真实 Qwen Plus 基线

2026 年 6 月 15 日首轮真实评测结果：

| 指标 | 首轮 |
|---|---:|
| 结果正确率 | 5/10，50% |
| 列结构匹配率 | 60% |
| 结果值匹配率 | 50% |
| 核心业务指标命中率 | 33.3% |
| 参考 SQL Guard / 执行 / 固定断言 | 100% |

首轮暴露两类真实问题：

1. `sales_amount`、`average_order_value`、`repeat_purchase_rate` 被模型改成中文别名或缩写，导致列契约漂移。
2. 按商品类别统计销售额时，模型在 `order_items` JOIN 后累加 `orders.total_amount`，造成订单总额重复计算。

没有通过放宽比较标准提高分数。修复方式是：

- 语义层明确每个指标的稳定英文输出别名。
- SQL 生成 prompt 强制使用稳定指标 key 和物理维度字段名。
- 销售额增加商品类别粒度覆盖表达式：`SUM(order_items.quantity * order_items.unit_price)`。

相同 10 条 case 复测结果：

| 指标 | 修复后 |
|---|---:|
| 结果正确率 | 10/10，100% |
| 列结构 / 结果值 / 排序匹配率 | 100% |
| 核心业务指标命中率 | 100% |
| 参考 SQL Guard / 执行 / 固定断言 | 100% |

## 7. CI 与安全边界

- 普通 PR CI 继续只运行确定性测试、Intent Evaluation、前端构建和 Secret Scan。
- 手动 `Real Qwen Evaluation` 在真实 NL2SQL/Repair 之后运行结果正确性评测，并统一上传报告。
- 第一版正确性指标只记录真实基线，不加入现有发布质量门禁。
- JSON 与 Markdown 报告过滤未知结果字段，不写入完整结果集或凭据。

## 8. 使用方式

```bash
cd backend
python -m evaluation.result_correctness_evaluator
```

报告默认写入 `backend/evaluation/reports/`，也可通过 `EVALUATION_REPORT_DIR` 指定隔离目录。

## 9. 后续路线

黄金基准证明了 Schema 和指标说明不足以保证正确聚合。下一阶段可建设 Schema Context Manager，根据问题只选择相关表、指标、维度和粒度规则，同时继续用本基准约束上下文裁剪不能造成正确率回退。
