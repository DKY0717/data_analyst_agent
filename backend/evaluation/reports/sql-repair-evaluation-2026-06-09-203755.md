# SQL Repair 故障注入评测报告

- 生成时间：2026-06-09-203755
- 总用例数：6
- 故障注入成功率：100.0%
- Repair 输出成功率：100.0%
- 修复后 Guard 通过率：100.0%
- 修复后执行成功率：83.3%
- 意图保持率：100.0%
- 端到端修复成功率：83.3%
- 平均修复后执行耗时：1.17 ms

## Case 明细

| Case | 故障注入 | Repair 输出 | Guard | 执行 | 意图保持 | 端到端成功 | 耗时(ms) |
|---|---|---|---|---|---|---|---:|
| wrong_order_amount_column | 是 | 是 | 是 | 是 | 是 | 是 | 0 |
| wrong_order_items_table | 是 | 是 | 是 | 是 | 是 | 是 | 3 |
| missing_customer_join | 是 | 是 | 是 | 是 | 是 | 是 | 2 |
| mysql_date_format | 是 | 是 | 是 | 是 | 是 | 是 | 1 |
| unsupported_quarter_format | 是 | 是 | 是 | 否 | 是 | 否 | 1 |
| wrong_region_column | 是 | 是 | 是 | 是 | 是 | 是 | 0 |

## 修复明细

### wrong_order_amount_column

- 说明：修复 orders 表中不存在的 revenue 字段
- 原始 SQL：`SELECT SUM(revenue) AS sales_amount FROM orders`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "revenue" not found in FROM clause!
Candidate bindings: "orders.status"
LINE 1: SELECT SUM(revenue) AS sales_amount FROM orders LI...
                   ^
- 修复 SQL：`SELECT SUM(total_amount) AS sales_amount FROM orders`
- 修复原因：原始 SQL 中引用了不存在的列 'revenue'，根据 schema，orders 表中对应销售金额的字段是 'total_amount'（DECIMAL 类型），而非 'revenue'。因此将 'revenue' 替换为 'total_amount' 即可修复列未找到的 Binder 错误。
- 最终错误：无

### wrong_order_items_table

- 说明：修复不存在的 order_detail 表
- 原始 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id`
- 原始数据库错误：数据库会话错误: Catalog Error: Table with name order_detail does not exist!
Did you mean "orders"?
LINE 1: ...d, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id LIMIT ...
                                                  ^
- 修复 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_items GROUP BY product_id`
- 修复原因：原始 SQL 中引用了不存在的表 'order_detail'，根据错误提示和数据库 Schema，正确表名为 'order_items'，其包含字段 product_id 和 quantity，符合查询需求。已将 FROM 子句中的表名修正为 'order_items'。
- 最终错误：无

### missing_customer_join

- 说明：修复查询客户名称时缺失的 customers 关联
- 原始 SQL：`SELECT order_id, customer_name FROM orders`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "customer_name" not found in FROM clause!
Candidate bindings: "orders.customer_id"
LINE 1: SELECT order_id, customer_name FROM orders LIMIT 1000
                         ^
- 修复 SQL：`SELECT o.order_id, c.customer_name FROM orders AS o JOIN customers AS c ON o.customer_id = c.customer_id`
- 修复原因：原始 SQL 中试图从 'orders' 表直接选择 'customer_name' 字段，但该字段并不存在于 'orders' 表中（orders 表只有 customer_id），而存在于 'customers' 表中。因此需要通过 JOIN 关联 orders 和 customers 表，基于 customer_id 字段进行连接，才能正确获取 customer_name。
- 最终错误：无

### mysql_date_format

- 说明：将 MySQL DATE_FORMAT 修复为 DuckDB 日期函数
- 原始 SQL：`SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY month`
- 原始数据库错误：数据库会话错误: Catalog Error: Scalar Function with name date_format does not exist!
Did you mean "format"?
LINE 1: SELECT DATE_FORMAT(order_date, '%Y-%m') AS mon...
               ^
- 修复 SQL：`SELECT strftime(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY strftime(order_date, '%Y-%m')`
- 修复原因：DuckDB 不支持 MySQL 风格的 DATE_FORMAT 函数；正确函数是 strftime()，用于格式化日期。原始 SQL 中使用了不存在的 DATE_FORMAT，且 GROUP BY 子句中不能直接引用 SELECT 中的别名 'month'（DuckDB 要求 GROUP BY 表达式需与 SELECT 中一致或显式重复），因此修复为使用 strftime(order_date, '%Y-%m') 在 SELECT 和 GROUP BY 中保持一致。
- 最终错误：无

### unsupported_quarter_format

- 说明：修复 DuckDB 不支持的 strftime 季度格式符
- 原始 SQL：`SELECT strftime(order_date, '%q') AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 原始数据库错误：数据库会话错误: Invalid Input Error: Failed to parse format specifier %q: Unrecognized format for strftime/strptime: %q
- 修复 SQL：`SELECT CAST((strftime('%m', order_date) - 1) / 3 + 1 AS INTEGER) AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 修复原因：DuckDB 不支持 strftime 的 '%q' 格式符（该格式符在 SQLite 中用于季度，但 DuckDB 尚未实现）。需手动计算季度：用 strftime('%m', order_date) 提取月份（1-12），减1后整除3再加1，即可得到 1~4 的季度编号。同时确保 GROUP BY 使用表达式或别名（DuckDB 支持按列别名分组，但为兼容性和明确性，此处使用相同表达式）。
- 最终错误：数据库会话错误: Binder Error: No function matches the given name and argument types '-(VARCHAR, INTEGER)'. You might need to add explicit type casts.
	Candidate functions:
	-(TINYINT) -> TINYINT
	-(TINYINT, TINYINT) -> TINYINT
	-(SMALLINT) -> SMALLINT
	-(SMALLINT, SMALLINT) -> SMALLINT
	-(INTEGER) -> INTEGER
	-(INTEGER, INTEGER) -> INTEGER
	-(BIGINT) -> BIGINT
	-(BIGINT, BIGINT) -> BIGINT
	-(HUGEINT) -> HUGEINT
	-(HUGEINT, HUGEINT) -> HUGEINT
	-(FLOAT) -> FLOAT
	-(FLOAT, FLOAT) -> FLOAT
	-(DOUBLE) -> DOUBLE
	-(DOUBLE, DOUBLE) -> DOUBLE
	-(DECIMAL) -> DECIMAL
	-(DECIMAL, DECIMAL) -> DECIMAL
	-(UTINYINT) -> UTINYINT
	-(UTINYINT, UTINYINT) -> UTINYINT
	-(USMALLINT) -> USMALLINT
	-(USMALLINT, USMALLINT) -> USMALLINT
	-(UINTEGER) -> UINTEGER
	-(UINTEGER, UINTEGER) -> UINTEGER
	-(UBIGINT) -> UBIGINT
	-(UBIGINT, UBIGINT) -> UBIGINT
	-(DATE, DATE) -> BIGINT
	-(DATE, INTEGER) -> DATE
	-(TIMESTAMP, TIMESTAMP) -> INTERVAL
	-(INTERVAL, INTERVAL) -> INTERVAL
	-(DATE, INTERVAL) -> DATE
	-(TIME, INTERVAL) -> TIME
	-(TIMESTAMP, INTERVAL) -> TIMESTAMP
	-(INTERVAL) -> INTERVAL
	-(TIMESTAMP WITH TIME ZONE, INTERVAL) -> TIMESTAMP WITH TIME ZONE
	-(TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE) -> INTERVAL

LINE 1: ...ELECT CAST((STRFTIME('%m', order_date) - 1) / 3 + 1 AS INT) AS quarter, SUM(to...
                                                  ^

### wrong_region_column

- 说明：修复 regions 表中不存在的 province_name 字段
- 原始 SQL：`SELECT province_name, COUNT(*) AS customer_count FROM regions GROUP BY province_name`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "province_name" not found in FROM clause!
Candidate bindings: "regions.province"
LINE 1: ...S customer_count FROM regions GROUP BY province_name LIMIT 1000
                                                  ^
- 修复 SQL：`SELECT province, COUNT(*) AS customer_count FROM regions GROUP BY province`
- 修复原因：错误原因是查询中引用了不存在的列 'province_name'，而表 'regions' 中实际对应的列为 'province'（根据 Schema 显示：regions 表包含字段 'province'，类型 VARCHAR，无 'province_name' 字段）。因此需将 SELECT 和 GROUP BY 中的 'province_name' 替换为正确的列名 'province'。
- 最终错误：无
