# database_design.md

## 1. 数据库设计目标

本数据库用于支撑 **Data Analyst Agent：自然语言驱动的数据库分析与 SQL 优化系统** 的第一版开发与演示。

数据库场景选择为电商业务数据分析，原因是该场景具有较好的展示性和扩展性，能够覆盖自然语言数据分析中的常见问题，例如：

1. 销售额统计；
2. 月度趋势分析；
3. 商品销量排行；
4. 用户复购率分析；
5. 地区销售表现分析；
6. 商品类别分析；
7. 支付方式分析；
8. 退款率分析；
9. 同比、环比分析；
10. SQL Join、Group By、Window Function 等复杂查询场景。

第一版数据库不追求业务系统级别的完整性，而是服务于以下目标：

1. 支持自然语言转 SQL；
2. 支持多表 Join 查询；
3. 支持聚合分析；
4. 支持时间序列分析；
5. 支持 SQL 优化场景构造；
6. 支持 SQL Guard、SQL Repair、SQL Optimizer 的测试。

---

## 2. 数据库类型

第一版推荐使用：

```text
DuckDB
```

原因：

1. 本地轻量，适合快速开发；
2. 不需要单独启动数据库服务；
3. 支持标准 SQL；
4. 支持分析型查询；
5. 支持 `EXPLAIN` 和 `EXPLAIN ANALYZE`；
6. 适合作为 Data Analyst Agent 的本地演示数据库。

后续增强版本可以增加：

```text
PostgreSQL
```

用于展示更接近企业真实环境的索引优化、执行计划分析和查询性能对比。

---

## 3. 数据库表总览

第一版包含 8 张核心表：

| 表名 | 中文含义 | 主要用途 |
|---|---|---|
| regions | 地区表 | 存储省份、城市、区域信息 |
| customers | 用户表 | 存储用户基础信息 |
| categories | 商品类别表 | 存储商品分类 |
| products | 商品表 | 存储商品基础信息 |
| orders | 订单表 | 存储订单主表信息 |
| order_items | 订单明细表 | 存储订单中的商品明细 |
| payments | 支付表 | 存储订单支付信息 |
| refunds | 退款表 | 存储订单退款信息 |

---

## 4. 表关系设计

### 4.1 关系概览

```text
regions 1 ─── n customers
customers 1 ─── n orders
orders 1 ─── n order_items
products 1 ─── n order_items
categories 1 ─── n products
orders 1 ─── 1 payments
orders 1 ─── 0..1 refunds
```

### 4.2 主外键关系

| 主表 | 主键 | 从表 | 外键 | 关系说明 |
|---|---|---|---|---|
| regions | region_id | customers | region_id | 一个地区对应多个用户 |
| customers | customer_id | orders | customer_id | 一个用户可以有多个订单 |
| orders | order_id | order_items | order_id | 一个订单可以包含多个商品 |
| products | product_id | order_items | product_id | 一个商品可以出现在多个订单明细中 |
| categories | category_id | products | category_id | 一个类别包含多个商品 |
| orders | order_id | payments | order_id | 一个订单对应一条支付记录 |
| orders | order_id | refunds | order_id | 一个订单可能有一条退款记录 |

---

## 5. 表结构详细设计

## 5.1 regions：地区表

### 5.1.1 表说明

`regions` 表用于存储地区信息，包括区域、省份和城市。该表主要用于地区销售分析、地区用户分布分析和地区复购率分析。

### 5.1.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| region_id | INTEGER | 是 | 否 | 地区 ID |
| region_name | VARCHAR | 否 | 否 | 大区名称，例如 East、South、North |
| province | VARCHAR | 否 | 否 | 省份 |
| city | VARCHAR | 否 | 否 | 城市 |

### 5.1.3 示例数据

| region_id | region_name | province | city |
|---|---|---|---|
| 1 | East | Zhejiang | Hangzhou |
| 2 | East | Shanghai | Shanghai |
| 3 | South | Guangdong | Guangzhou |
| 4 | North | Beijing | Beijing |

### 5.1.4 常见查询问题

1. 统计不同地区的客户数量；
2. 统计不同地区的销售额；
3. 分析不同地区的复购率；
4. 找出销售额最高的城市。

---

## 5.2 customers：用户表

### 5.2.1 表说明

`customers` 表用于存储用户基础信息，包括用户 ID、姓名、性别、年龄、所属地区和注册日期。该表主要用于用户画像分析、地区分析和复购率分析。

### 5.2.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| customer_id | INTEGER | 是 | 否 | 用户 ID |
| customer_name | VARCHAR | 否 | 否 | 用户姓名 |
| gender | VARCHAR | 否 | 否 | 性别，Male/Female |
| age | INTEGER | 否 | 否 | 年龄 |
| region_id | INTEGER | 否 | 是 | 地区 ID，关联 regions.region_id |
| register_date | DATE | 否 | 否 | 注册日期 |

### 5.2.3 示例数据

| customer_id | customer_name | gender | age | region_id | register_date |
|---|---|---|---|---|---|
| 1 | Customer_1 | Female | 28 | 1 | 2022-03-15 |
| 2 | Customer_2 | Male | 35 | 3 | 2023-06-21 |

### 5.2.4 常见查询问题

1. 统计用户总数；
2. 统计不同地区的用户数量；
3. 统计不同年龄段用户的消费金额；
4. 统计 2024 年新注册用户数量；
5. 分析高价值客户的地区分布。

---

## 5.3 categories：商品类别表

### 5.3.1 表说明

`categories` 表用于存储商品类别信息，例如 Electronics、Clothing、Food、Home 等。该表主要用于商品类别维度的销售额、退款率和利润分析。

### 5.3.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| category_id | INTEGER | 是 | 否 | 商品类别 ID |
| category_name | VARCHAR | 否 | 否 | 商品类别名称 |

### 5.3.3 示例数据

| category_id | category_name |
|---|---|
| 1 | Electronics |
| 2 | Clothing |
| 3 | Food |
| 4 | Home |

### 5.3.4 常见查询问题

1. 统计每个商品类别的销售额；
2. 统计每个商品类别的订单数量；
3. 统计每个商品类别的退款率；
4. 找出销售额最高的商品类别。

---

## 5.4 products：商品表

### 5.4.1 表说明

`products` 表用于存储商品基础信息，包括商品 ID、商品名称、类别、价格、成本和上架日期。该表主要用于商品销售分析、类别分析和利润分析。

### 5.4.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| product_id | INTEGER | 是 | 否 | 商品 ID |
| product_name | VARCHAR | 否 | 否 | 商品名称 |
| category_id | INTEGER | 否 | 是 | 商品类别 ID，关联 categories.category_id |
| price | DECIMAL(10,2) | 否 | 否 | 商品标价 |
| cost | DECIMAL(10,2) | 否 | 否 | 商品成本 |
| created_at | DATE | 否 | 否 | 商品上架日期 |

### 5.4.3 示例数据

| product_id | product_name | category_id | price | cost | created_at |
|---|---|---|---|---|---|
| 1 | Product_1 | 1 | 199.00 | 120.00 | 2022-01-10 |
| 2 | Product_2 | 2 | 89.00 | 45.00 | 2023-04-20 |

### 5.4.4 常见查询问题

1. 找出销售额最高的前 10 个商品；
2. 找出销量最高的前 10 个商品；
3. 统计每个商品类别的销售额；
4. 统计每个商品的毛利润；
5. 找出退款金额最高的商品。

---

## 5.5 orders：订单表

### 5.5.1 表说明

`orders` 表是订单主表，用于存储订单级别信息，包括订单 ID、用户 ID、下单日期、订单状态和订单总金额。该表是销售分析的核心表。

### 5.5.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| order_id | INTEGER | 是 | 否 | 订单 ID |
| customer_id | INTEGER | 否 | 是 | 用户 ID，关联 customers.customer_id |
| order_date | DATE | 否 | 否 | 下单日期 |
| status | VARCHAR | 否 | 否 | 订单状态，例如 Completed、Cancelled、Refunded |
| total_amount | DECIMAL(10,2) | 否 | 否 | 订单总金额 |

### 5.5.3 示例数据

| order_id | customer_id | order_date | status | total_amount |
|---|---|---|---|---|
| 1 | 15 | 2024-01-05 | Completed | 358.00 |
| 2 | 27 | 2024-01-06 | Refunded | 129.00 |

### 5.5.4 常见查询问题

1. 统计订单总数；
2. 统计 2024 年销售额；
3. 统计每个月销售额；
4. 统计订单状态分布；
5. 计算客单价；
6. 计算用户复购率；
7. 计算同比增长率和环比增长率。

---

## 5.6 order_items：订单明细表

### 5.6.1 表说明

`order_items` 表用于存储订单中的商品明细。一个订单可以包含多个商品，因此该表用于连接订单和商品，是商品销售分析的核心表。

### 5.6.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| item_id | INTEGER | 是 | 否 | 订单明细 ID |
| order_id | INTEGER | 否 | 是 | 订单 ID，关联 orders.order_id |
| product_id | INTEGER | 否 | 是 | 商品 ID，关联 products.product_id |
| quantity | INTEGER | 否 | 否 | 商品购买数量 |
| unit_price | DECIMAL(10,2) | 否 | 否 | 商品成交单价 |

### 5.6.3 示例数据

| item_id | order_id | product_id | quantity | unit_price |
|---|---|---|---|---|
| 1 | 1 | 3 | 2 | 99.00 |
| 2 | 1 | 8 | 1 | 160.00 |

### 5.6.4 常见查询问题

1. 找出销量最高的商品；
2. 统计每个商品的销售额；
3. 统计每个类别的销售额；
4. 分析商品销售数量分布；
5. 计算订单中平均商品数量。

---

## 5.7 payments：支付表

### 5.7.1 表说明

`payments` 表用于存储订单支付信息，包括支付方式、支付状态、支付金额和支付时间。该表用于支付方式分析和支付成功率分析。

### 5.7.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| payment_id | INTEGER | 是 | 否 | 支付 ID |
| order_id | INTEGER | 否 | 是 | 订单 ID，关联 orders.order_id |
| payment_method | VARCHAR | 否 | 否 | 支付方式，例如 Credit Card、Alipay、WeChat Pay、PayPal |
| payment_status | VARCHAR | 否 | 否 | 支付状态，例如 Paid、Failed、Pending |
| paid_amount | DECIMAL(10,2) | 否 | 否 | 实际支付金额 |
| paid_at | TIMESTAMP | 否 | 否 | 支付时间 |

### 5.7.3 示例数据

| payment_id | order_id | payment_method | payment_status | paid_amount | paid_at |
|---|---|---|---|---|---|
| 1 | 1 | Alipay | Paid | 358.00 | 2024-01-05 10:30:00 |
| 2 | 2 | Credit Card | Paid | 129.00 | 2024-01-06 15:20:00 |

### 5.7.4 常见查询问题

1. 统计不同支付方式的订单数量；
2. 统计不同支付方式的销售额；
3. 计算支付成功率；
4. 分析不同支付方式的平均订单金额。

---

## 5.8 refunds：退款表

### 5.8.1 表说明

`refunds` 表用于存储订单退款信息，包括退款金额、退款原因和退款日期。该表用于退款率分析、退款原因分析和商品质量问题分析。

### 5.8.2 字段设计

| 字段名 | 类型 | 是否主键 | 是否外键 | 含义 |
|---|---|---|---|---|
| refund_id | INTEGER | 是 | 否 | 退款 ID |
| order_id | INTEGER | 否 | 是 | 订单 ID，关联 orders.order_id |
| refund_amount | DECIMAL(10,2) | 否 | 否 | 退款金额 |
| refund_reason | VARCHAR | 否 | 否 | 退款原因 |
| refund_date | DATE | 否 | 否 | 退款日期 |

### 5.8.3 示例数据

| refund_id | order_id | refund_amount | refund_reason | refund_date |
|---|---|---|---|---|
| 1 | 2 | 129.00 | Quality Issue | 2024-01-10 |

### 5.8.4 常见查询问题

1. 统计总退款金额；
2. 计算订单退款率；
3. 分析不同商品类别的退款率；
4. 分析退款原因分布；
5. 找出退款金额最高的商品或类别。

---

## 6. 支持的核心分析指标

## 6.1 销售额 Sales

定义：

```text
销售额 = completed 订单的 total_amount 之和
```

常用 SQL 逻辑：

```sql
SUM(total_amount)
```

主要涉及表：

```text
orders
```

---

## 6.2 订单数 Order Count

定义：

```text
订单数 = orders 表中的订单数量
```

常用 SQL 逻辑：

```sql
COUNT(DISTINCT order_id)
```

主要涉及表：

```text
orders
```

---

## 6.3 客单价 Average Order Value，AOV

定义：

```text
客单价 = 销售额 / 订单数
```

常用 SQL 逻辑：

```sql
SUM(total_amount) / COUNT(DISTINCT order_id)
```

主要涉及表：

```text
orders
```

---

## 6.4 商品销量 Quantity Sold

定义：

```text
商品销量 = order_items.quantity 之和
```

常用 SQL 逻辑：

```sql
SUM(quantity)
```

主要涉及表：

```text
order_items
products
```

---

## 6.5 复购率 Repeat Purchase Rate

定义：

```text
复购率 = 下单次数大于等于 2 的用户数 / 下过单的用户数
```

常用 SQL 逻辑：

```sql
COUNT(CASE WHEN order_count >= 2 THEN customer_id END) / COUNT(customer_id)
```

主要涉及表：

```text
customers
orders
```

---

## 6.6 退款率 Refund Rate

可定义为订单维度退款率：

```text
退款率 = 有退款记录的订单数 / 总订单数
```

也可定义为金额维度退款率：

```text
金额退款率 = 退款金额 / 销售额
```

主要涉及表：

```text
orders
refunds
```

---

## 6.7 毛利润 Gross Profit

定义：

```text
毛利润 = 商品成交收入 - 商品成本
```

常用 SQL 逻辑：

```sql
SUM((unit_price - cost) * quantity)
```

主要涉及表：

```text
order_items
products
```

---

## 6.8 同比增长率 YoY Growth

定义：

```text
同比增长率 = (本期指标 - 去年同期指标) / 去年同期指标
```

主要涉及场景：

```text
月度销售额同比
季度销售额同比
地区销售额同比
商品类别销售额同比
```

---

## 7. 典型自然语言问题与涉及表

| 自然语言问题 | 涉及表 | 查询类型 |
|---|---|---|
| 统计 2024 年每个月的销售额 | orders | 时间序列聚合 |
| 找出销售额最高的前 10 个商品 | orders, order_items, products | 多表 Join + 排名 |
| 统计不同地区的客户数量 | customers, regions | Join + Group By |
| 计算不同地区的销售额 | orders, customers, regions | 多表 Join + 聚合 |
| 分析每个商品类别的销售额 | orders, order_items, products, categories | 多表 Join + 聚合 |
| 统计每种支付方式的订单数量 | payments | Group By |
| 计算订单退款率 | orders, refunds | Join + 比率计算 |
| 统计不同商品类别的退款率 | orders, refunds, order_items, products, categories | 多表 Join + 比率计算 |
| 计算用户复购率 | orders | 分组统计 + 比率计算 |
| 计算 2024 年销售额同比增长率 | orders | 时间序列 + 窗口/自连接 |

---

## 8. SQL 优化测试场景设计

本数据库也用于构造 SQL 优化测试场景。

### 8.1 SELECT * 场景

低效 SQL：

```sql
SELECT * FROM orders;
```

优化建议：

```text
只查询必要字段，并添加 LIMIT。
```

---

### 8.2 时间字段函数包裹场景

低效 SQL：

```sql
SELECT SUM(total_amount)
FROM orders
WHERE EXTRACT(YEAR FROM order_date) = 2024;
```

优化建议：

```sql
SELECT SUM(total_amount)
FROM orders
WHERE order_date >= '2024-01-01'
  AND order_date < '2025-01-01';
```

原因：

```text
使用范围查询更有利于利用日期索引。
```

---

### 8.3 大表 Join 前未过滤场景

低效 SQL：

```sql
SELECT r.region_name, SUM(o.total_amount)
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN regions r ON c.region_id = r.region_id
GROUP BY r.region_name;
```

优化建议：

```text
如果只分析 2024 年数据，应先在 orders 表中进行时间过滤，再执行 Join。
```

---

### 8.4 重复子查询场景

低效 SQL：

```sql
SELECT
  customer_id,
  (SELECT COUNT(*) FROM orders o2 WHERE o2.customer_id = o1.customer_id) AS order_count
FROM orders o1;
```

优化建议：

```text
使用 GROUP BY 或 CTE 替代重复相关子查询。
```

---

## 9. 第一版模拟数据规模建议

为了兼顾运行速度和查询展示效果，第一版建议生成以下规模：

| 表名 | 数据量建议 |
|---|---|
| regions | 20 |
| customers | 1,000 |
| categories | 8 |
| products | 300 |
| orders | 10,000 |
| order_items | 20,000 - 30,000 |
| payments | 10,000 |
| refunds | 500 - 1,500 |

第二版如果要展示 SQL 优化前后耗时变化，可以扩大为：

| 表名 | 数据量建议 |
|---|---|
| customers | 50,000 |
| products | 2,000 |
| orders | 500,000 |
| order_items | 1,000,000+ |

---

## 10. 数据生成原则

`seed_data.py` 需要满足以下要求：

1. 使用固定随机种子，保证数据可复现；
2. 订单日期覆盖 2022 年到 2025 年；
3. 不同地区、商品类别、支付方式有一定差异；
4. 部分用户拥有多笔订单，用于复购率分析；
5. 部分订单存在退款记录，用于退款率分析；
6. 商品价格和成本存在合理差异，用于利润分析；
7. 订单状态包括 Completed、Cancelled、Refunded；
8. 支付状态包括 Paid、Failed、Pending；
9. 订单金额应与订单明细金额基本一致；
10. 数据不能过于均匀，否则分析结果缺乏展示价值。

---

## 11. 字段命名规范

1. 表名使用小写复数形式，例如 `orders`、`customers`；
2. 字段名使用 snake_case，例如 `order_id`、`total_amount`；
3. 主键统一使用 `{entity}_id`；
4. 外键字段名与关联主键保持一致；
5. 日期字段使用 `_date` 后缀；
6. 时间戳字段使用 `_at` 后缀；
7. 金额字段使用 `_amount` 后缀。

---

## 12. 后续扩展表，可选

如果后续希望增强项目复杂度，可以增加以下表：

| 表名 | 含义 | 用途 |
|---|---|---|
| campaigns | 营销活动表 | 分析营销活动效果 |
| product_reviews | 商品评价表 | 分析评分和销量关系 |
| inventory | 库存表 | 分析库存周转 |
| coupons | 优惠券表 | 分析优惠券使用效果 |
| customer_segments | 用户分层表 | 分析高价值用户 |
| web_events | 用户行为日志表 | 分析浏览、加购、转化 |

第一版暂时不加入这些表，避免复杂度过高。

---

## 13. 本文档对应开发任务

根据本数据库设计，后续需要生成以下文件：

```text
database/init.sql
database/seed_data.py
backend/app/db/schema_loader.py
evaluation/test_questions.json
```

开发顺序建议：

```text
1. 根据本文档生成 init.sql
2. 根据本文档生成 seed_data.py
3. 运行 seed_data.py 生成 DuckDB 数据库
4. 手写 SQL 验证核心分析问题
5. 实现 Schema Loader
6. 接入 SQL Generator
```

---

## 14. 验收标准

数据库部分完成后，需要满足以下验收标准：

1. 能够成功创建全部 8 张表；
2. 能够成功插入模拟数据；
3. 主外键关系逻辑清晰；
4. 能够支持至少 30 个自然语言分析问题；
5. 能够手写 SQL 完成销售额、退款率、复购率、商品排行、地区分析；
6. 能够为 SQL Guard、SQL Repair、SQL Optimizer 提供测试场景；
7. 数据量适合本地运行，不影响开发体验。

