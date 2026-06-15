# 结果正确性黄金基准报告

- 生成时间：2026-06-15-154801
- 总用例数：10
- 结果正确率：50.0%
- 列结构匹配率：60.0%
- 结果值匹配率：50.0%
- 排序匹配率：100.0%
- 核心业务指标命中率：33.3%
- 参考 SQL Guard 通过率：100.0%
- 参考 SQL 执行成功率：100.0%
- 固定断言通过率：100.0%

## 失败 Case 明细

### sales_by_region

- 分类：dimension
- 问题：统计 2024 年各地区的销售额
- 失败类型：column_mismatch
- Agent SQL：`SELECT r.region_name, SUM(o.total_amount) AS 销售额 FROM orders AS o JOIN customers AS c ON o.customer_id = c.customer_id JOIN regions AS r ON c.region_id = r.region_id WHERE STRFTIME(o.order_date, '%Y') = '2024' GROUP BY r.region_name ORDER BY 销售额 DESC LIMIT 1000`
- 有限差异样本：[{"actual_columns": ["region_name", "销售额"], "expected_columns": ["region_name", "sales_amount"], "required_columns": ["region_name", "sales_amount"]}]

### sales_by_category

- 分类：aggregation
- 问题：统计各商品类别的销售额
- 失败类型：value_mismatch
- Agent SQL：`SELECT c.category_name, SUM(o.total_amount) AS sales_amount FROM orders AS o JOIN order_items AS oi ON o.order_id = oi.order_id JOIN products AS p ON oi.product_id = p.product_id JOIN categories AS c ON p.category_id = c.category_id GROUP BY c.category_name ORDER BY sales_amount DESC LIMIT 1000`
- 有限差异样本：[{"actual": ["Electronics", "521131.00"], "expected": null}, {"actual": ["Home", "250523.00"], "expected": null}, {"actual": ["Clothing", "243494.00"], "expected": null}, {"actual": ["Sports", "204047.00"], "expected": null}, {"actual": ["Beauty", "202667.00"], "expected": null}]

### average_order_value_2024

- 分类：business_metric
- 问题：计算 2024 年的平均客单价
- 失败类型：column_mismatch
- Agent SQL：`SELECT SUM(o.total_amount) * 1.0 / COUNT(DISTINCT o.order_id) AS avg_order_value FROM orders AS o WHERE o.order_date >= '2024-01-01' AND o.order_date < '2025-01-01' LIMIT 1000`
- 有限差异样本：[{"actual_columns": ["avg_order_value"], "expected_columns": ["average_order_value"], "required_columns": ["average_order_value"]}]

### repeat_purchase_rate

- 分类：business_metric
- 问题：计算客户复购率
- 失败类型：column_mismatch
- Agent SQL：`WITH customer_order_stats AS (SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS order_count FROM orders AS o GROUP BY o.customer_id) SELECT COUNT(DISTINCT CASE WHEN cos.order_count > 1 THEN cos.customer_id END) * 1.0 / COUNT(DISTINCT cos.customer_id) AS 复购率 FROM customer_order_stats AS cos LIMIT 1000`
- 有限差异样本：[{"actual_columns": ["复购率"], "expected_columns": ["repeat_purchase_rate"], "required_columns": ["repeat_purchase_rate"]}]

### payment_method_sales

- 分类：dimension
- 问题：统计各支付方式对应的销售额
- 失败类型：column_mismatch
- Agent SQL：`SELECT p.payment_method, SUM(o.total_amount) AS 销售额 FROM orders AS o JOIN payments AS p ON o.order_id = p.order_id GROUP BY p.payment_method ORDER BY 销售额 DESC LIMIT 1000`
- 有限差异样本：[{"actual_columns": ["payment_method", "销售额"], "expected_columns": ["payment_method", "sales_amount"], "required_columns": ["payment_method", "sales_amount"]}]
