# SQL Repair 故障注入评测报告

- 生成时间：2026-06-09-204019
- 总用例数：6
- 故障注入成功率：100.0%
- Repair 输出成功率：100.0%
- 修复后 Guard 通过率：100.0%
- 修复后执行成功率：100.0%
- 意图保持率：100.0%
- 端到端修复成功率：100.0%
- 平均修复后执行耗时：1.17 ms

## Case 明细

| Case | 故障注入 | Repair 输出 | Guard | 执行 | 意图保持 | 端到端成功 | 耗时(ms) |
|---|---|---|---|---|---|---|---:|
| wrong_order_amount_column | 是 | 是 | 是 | 是 | 是 | 是 | 0 |
| wrong_order_items_table | 是 | 是 | 是 | 是 | 是 | 是 | 3 |
| missing_customer_join | 是 | 是 | 是 | 是 | 是 | 是 | 2 |
| mysql_date_format | 是 | 是 | 是 | 是 | 是 | 是 | 1 |
| unsupported_quarter_format | 是 | 是 | 是 | 是 | 是 | 是 | 0 |
| wrong_region_column | 是 | 是 | 是 | 是 | 是 | 是 | 1 |

## 修复明细

### wrong_order_amount_column

- 说明：修复 orders 表中不存在的 revenue 字段
- 原始 SQL：`SELECT SUM(revenue) AS sales_amount FROM orders`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "revenue" not found in FROM clause!
Candidate bindings: "orders.status"
LINE 1: SELECT SUM(revenue) AS sales_amount FROM orders LI...
                   ^
- 修复 SQL：`SELECT SUM(total_amount) AS sales_amount FROM orders`
- 修复原因：错误原因是原始 SQL 中引用了不存在的列 'revenue'，而根据数据库 Schema，orders 表中对应的销售额字段是 'total_amount'（DECIMAL 类型），并非 'revenue'。因此将 SUM(revenue) 替换为 SUM(total_amount) 即可修复。
- 最终错误：无

### wrong_order_items_table

- 说明：修复不存在的 order_detail 表
- 原始 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id`
- 原始数据库错误：数据库会话错误: Catalog Error: Table with name order_detail does not exist!
Did you mean "orders"?
LINE 1: ...d, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id LIMIT ...
                                                  ^
- 修复 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_items GROUP BY product_id`
- 修复原因：原始 SQL 中引用了不存在的表 'order_detail'，根据错误提示和数据库 Schema，正确的表名为 'order_items'，其包含字段 product_id 和 quantity，符合查询意图（按商品统计销量）。已将 FROM 子句中的表名修正为 'order_items'。
- 最终错误：无

### missing_customer_join

- 说明：修复查询客户名称时缺失的 customers 关联
- 原始 SQL：`SELECT order_id, customer_name FROM orders`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "customer_name" not found in FROM clause!
Candidate bindings: "orders.customer_id"
LINE 1: SELECT order_id, customer_name FROM orders LIMIT 1000
                         ^
- 修复 SQL：`SELECT o.order_id, c.customer_name FROM orders o JOIN customers c ON o.customer_id = c.customer_id`
- 修复原因：原始 SQL 中试图从 'orders' 表直接选择 'customer_name' 字段，但该字段并不存在于 'orders' 表中（仅存在 'customer_id'）；'customer_name' 实际位于 'customers' 表。因此需通过 JOIN 关联 'orders' 和 'customers' 表（基于 customer_id），才能正确获取 customer_name。
- 最终错误：无

### mysql_date_format

- 说明：将 MySQL DATE_FORMAT 修复为 DuckDB 日期函数
- 原始 SQL：`SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY month`
- 原始数据库错误：数据库会话错误: Catalog Error: Scalar Function with name date_format does not exist!
Did you mean "format"?
LINE 1: SELECT DATE_FORMAT(order_date, '%Y-%m') AS mon...
               ^
- 修复 SQL：`SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY strftime('%Y-%m', order_date)`
- 修复原因：原始 SQL 使用了 MySQL 风格的 DATE_FORMAT 函数，但当前数据库（DuckDB）不支持该函数，错误提示建议使用 'format'，但 DuckDB 中日期格式化应使用 strftime() 函数。strftime('%Y-%m', order_date) 可正确提取年月字符串（如 '2023-05'），且 GROUP BY 需与 SELECT 中的表达式一致（不能直接用别名 month，因 DuckDB 不支持在 GROUP BY 中直接引用列别名），故需重复 strftime 表达式。
- 最终错误：无

### unsupported_quarter_format

- 说明：修复 DuckDB 不支持的 strftime 季度格式符
- 原始 SQL：`SELECT strftime(order_date, '%q') AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 原始数据库错误：数据库会话错误: Invalid Input Error: Failed to parse format specifier %q: Unrecognized format for strftime/strptime: %q
- 修复 SQL：`SELECT EXTRACT(QUARTER FROM order_date) AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 修复原因：DuckDB 不支持 strftime 的 '%q' 格式符（该格式符在 SQLite 中用于提取季度，但在 DuckDB 中无效）。应改用标准 SQL 的 EXTRACT(QUARTER FROM date_column) 函数来获取季度数值。此外，原始 SQL 中 GROUP BY quarter 引用了别名，在 DuckDB 中允许，但为确保兼容性和清晰性，仍推荐使用该写法；同时需注意 EXTRACT 返回的是 INTEGER 类型，符合分组和聚合需求。
- 最终错误：无

### wrong_region_column

- 说明：修复 regions 表中不存在的 province_name 字段
- 原始 SQL：`SELECT province_name, COUNT(*) AS customer_count FROM regions GROUP BY province_name`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "province_name" not found in FROM clause!
Candidate bindings: "regions.province"
LINE 1: ...S customer_count FROM regions GROUP BY province_name LIMIT 1000
                                                  ^
- 修复 SQL：`SELECT province, COUNT(*) AS customer_count FROM regions GROUP BY province`
- 修复原因：错误原因是原始 SQL 中引用了不存在的列名 'province_name'，而根据 Schema，表 'regions' 中实际存在的列是 'province'（类型 VARCHAR）。因此需将 SELECT 和 GROUP BY 子句中的 'province_name' 替换为正确的列名 'province'。
- 最终错误：无
