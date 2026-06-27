# v0.6 分层意图与 Schema Grounding 评测报告

- 生成时间：2026-06-25-204354
- 总用例数：7
- 槽位整体匹配率：100.0%
- Grounding 候选命中率：100.0%
- 路由表召回率：100.0%
- 澄清决策准确率：100.0%
- 澄清候选命中率：100.0%
- 全部预期满足率：100.0%
- 质量门禁：通过

## Case 明细

| Case | 分类 | 槽位 | 候选 | 路由 | 澄清决策 | 澄清候选 | 结果 |
|---|---|---|---|---|---|---|---|
| sales_by_region_2024 | metric_dimension_filter | 是 | 是 | 是 | 是 | 是 | 是 |
| category_sales_uses_item_amount_candidate | metric_dimension_grounding | 是 | 是 | 是 | 是 | 是 | 是 |
| refund_rate_by_category | metric_dimension_grounding | 是 | 是 | 是 | 是 | 是 | 是 |
| monthly_order_count | time_dimension | 是 | 是 | 是 | 是 | 是 | 是 |
| top_region_customer_count | ranking | 是 | 是 | 是 | 是 | 是 | 是 |
| quarter_sales | time_dimension | 是 | 是 | 是 | 是 | 是 | 是 |
| vague_analysis_requires_metric_clarification | clarification | 是 | 是 | 是 | 是 | 是 | 是 |

## 失败明细

- 无
