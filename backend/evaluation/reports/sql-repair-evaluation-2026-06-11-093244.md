# SQL Repair 故障注入评测报告

- 生成时间：2026-06-11-093244
- 总用例数：6
- 故障注入成功率：100.0%
- Repair 输出成功率：100.0%
- 修复后 Guard 通过率：100.0%
- 修复后执行成功率：100.0%
- 意图保持率：100.0%
- 端到端修复成功率：100.0%
- 平均修复后执行耗时：2.67 ms
- 平均 LLM 调用次数：1.00
- 平均 LLM Token：865.83
- 平均 LLM 耗时：3061.17 ms
- LLM 估算总成本：未配置价格

## Case 明细

| Case | 故障注入 | Repair 输出 | Guard | 执行 | 意图保持 | 端到端成功 | DB耗时(ms) | LLM调用 | Token | LLM耗时(ms) |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| wrong_order_amount_column | 是 | 是 | 是 | 是 | 是 | 是 | 1 | 1 | 835 | 3005 |
| wrong_order_items_table | 是 | 是 | 是 | 是 | 是 | 是 | 0 | 1 | 855 | 2597 |
| missing_customer_join | 是 | 是 | 是 | 是 | 是 | 是 | 3 | 1 | 872 | 3824 |
| mysql_date_format | 是 | 是 | 是 | 是 | 是 | 是 | 1 | 1 | 922 | 3521 |
| unsupported_quarter_format | 是 | 是 | 是 | 是 | 是 | 是 | 11 | 1 | 870 | 3079 |
| wrong_region_column | 是 | 是 | 是 | 是 | 是 | 是 | 0 | 1 | 841 | 2341 |

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
- LLM 估算成本：未配置价格

### wrong_order_items_table

- 说明：修复不存在的 order_detail 表
- 原始 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id`
- 原始数据库错误：数据库会话错误: Catalog Error: Table with name order_detail does not exist!
Did you mean "orders"?
LINE 1: ...d, SUM(quantity) AS quantity_sold FROM order_detail GROUP BY product_id LIMIT ...
                                                  ^
- 修复 SQL：`SELECT product_id, SUM(quantity) AS quantity_sold FROM order_items GROUP BY product_id`
- 修复原因：原始 SQL 中引用了不存在的表 'order_detail'，根据数据库 Schema，存储订单明细（含 product_id 和 quantity）的表实际名为 'order_items'。已将 FROM 子句中的表名修正为 'order_items'，其余逻辑（按 product_id 聚合计量）保持不变。
- 最终错误：无
- LLM 估算成本：未配置价格

### missing_customer_join

- 说明：修复查询客户名称时缺失的 customers 关联
- 原始 SQL：`SELECT order_id, customer_name FROM orders`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "customer_name" not found in FROM clause!
Candidate bindings: "orders.customer_id"
LINE 1: SELECT order_id, customer_name FROM orders LIMIT 1000
                         ^
- 修复 SQL：`SELECT o.order_id, c.customer_name FROM orders AS o JOIN customers AS c ON o.customer_id = c.customer_id`
- 修复原因：原始 SQL 中试图从 'orders' 表直接选择 'customer_name' 字段，但该字段并不存在于 'orders' 表中（仅存在于 'customers' 表）。需通过 JOIN 关联 'orders' 和 'customers' 表（基于 customer_id），才能获取 customer_name。修复后使用表别名 o 和 c 提高可读性，并正确关联两表。
- 最终错误：无
- LLM 估算成本：未配置价格

### mysql_date_format

- 说明：将 MySQL DATE_FORMAT 修复为 DuckDB 日期函数
- 原始 SQL：`SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY month`
- 原始数据库错误：数据库会话错误: Catalog Error: Scalar Function with name date_format does not exist!
Did you mean "format"?
LINE 1: SELECT DATE_FORMAT(order_date, '%Y-%m') AS mon...
               ^
- 修复 SQL：`SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS sales_amount FROM orders GROUP BY strftime('%Y-%m', order_date)`
- 修复原因：DuckDB 不支持 MySQL 风格的 DATE_FORMAT 函数，错误提示建议使用 'format'，但实际 DuckDB 中日期格式化应使用 strftime() 函数。strftime('%Y-%m', order_date) 可正确提取年月字符串（如 '2023-05'）。注意：GROUP BY 必须与 SELECT 中的表达式一致（不能直接用别名 month，因 DuckDB 在 GROUP BY 中不支持引用 SELECT 别名），故需重复 strftime 表达式。
- 最终错误：无
- LLM 估算成本：未配置价格

### unsupported_quarter_format

- 说明：修复 DuckDB 不支持的 strftime 季度格式符
- 原始 SQL：`SELECT strftime(order_date, '%q') AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 原始数据库错误：数据库会话错误: Invalid Input Error: Failed to parse format specifier %q: Unrecognized format for strftime/strptime: %q
- 修复 SQL：`SELECT EXTRACT(QUARTER FROM order_date) AS quarter, SUM(total_amount) AS sales_amount FROM orders GROUP BY quarter`
- 修复原因：DuckDB 不支持 strftime 的 '%q' 格式符（该格式符在 SQLite 中可用，但 DuckDB 不兼容）。应改用标准 SQL 函数 EXTRACT(QUARTER FROM date_column) 来提取季度。此外，strftime 返回字符串类型，而季度需参与数值分组和排序，EXTRACT 直接返回 INTEGER，语义更准确且避免隐式转换问题。
- 最终错误：无
- LLM 估算成本：未配置价格

### wrong_region_column

- 说明：修复 regions 表中不存在的 province_name 字段
- 原始 SQL：`SELECT province_name, COUNT(*) AS customer_count FROM regions GROUP BY province_name`
- 原始数据库错误：数据库会话错误: Binder Error: Referenced column "province_name" not found in FROM clause!
Candidate bindings: "regions.province"
LINE 1: ...S customer_count FROM regions GROUP BY province_name LIMIT 1000
                                                  ^
- 修复 SQL：`SELECT province, COUNT(*) AS customer_count FROM regions GROUP BY province`
- 修复原因：错误原因是查询中引用了不存在的列 'province_name'；根据 Schema，regions 表中实际字段名为 'province'（而非 'province_name'），因此需将 SELECT 和 GROUP BY 中的 'province_name' 替换为 'province'。
- 最终错误：无
- LLM 估算成本：未配置价格
