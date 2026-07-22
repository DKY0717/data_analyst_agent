# Spider → 电商 Schema 转换器
# 将 Spider 数据集的 NL2SQL case 转换为适配电商 schema 的版本

import yaml
from pathlib import Path
from typing import Any, Dict, List

SPIDER_CASES_FILE = Path(__file__).parent / "cases" / "spider_nl2sql_cases.yaml"
OUTPUT_FILE = Path(__file__).parent / "cases" / "ecommerce_spider_cases.yaml"

# 电商 Schema 定义
ECOMMERCE_SCHEMA = {
    "regions": ["region_id", "region_name", "province", "city"],
    "customers": ["customer_id", "customer_name", "gender", "age", "region_id", "register_date"],
    "categories": ["category_id", "category_name"],
    "products": ["product_id", "product_name", "category_id", "price", "cost", "created_at"],
    "orders": ["order_id", "customer_id", "order_date", "status", "total_amount"],
    "order_items": ["item_id", "order_id", "product_id", "quantity", "unit_price"],
    "payments": ["payment_id", "order_id", "payment_method", "payment_status", "paid_amount", "paid_at"],
    "refunds": ["refund_id", "order_id", "refund_amount", "refund_reason", "refund_date"],
}

# SQL 模式 → 电商映射规则
MAPPING_RULES = [
    # 简单计数
    {
        "pattern": "COUNT(*)",
        "question_templates": [
            ("统计客户总数", "SELECT COUNT(*) FROM customers"),
            ("统计订单总数", "SELECT COUNT(*) FROM orders"),
            ("统计商品总数", "SELECT COUNT(*) FROM products"),
            ("统计地区总数", "SELECT COUNT(*) FROM regions"),
        ],
        "difficulty": "easy",
        "category": "simple_select",
    },
    # 平均值/最大/最小
    {
        "pattern": "AVG",
        "question_templates": [
            ("计算客户的平均年龄", "SELECT AVG(age) FROM customers"),
            ("计算订单的平均金额", "SELECT AVG(total_amount) FROM orders"),
            ("计算商品的平均价格", "SELECT AVG(price) FROM products"),
        ],
        "difficulty": "easy",
        "category": "simple_select",
    },
    {
        "pattern": "MAX",
        "question_templates": [
            ("查询最高的订单金额", "SELECT MAX(total_amount) FROM orders"),
            ("查询最贵的商品价格", "SELECT MAX(price) FROM products"),
            ("查询最大的客户年龄", "SELECT MAX(age) FROM customers"),
        ],
        "difficulty": "easy",
        "category": "simple_select",
    },
    {
        "pattern": "MIN",
        "question_templates": [
            ("查询最低的订单金额", "SELECT MIN(total_amount) FROM orders"),
            ("查询最便宜的商品价格", "SELECT MIN(price) FROM products"),
            ("查询最小的客户年龄", "SELECT MIN(age) FROM customers"),
        ],
        "difficulty": "easy",
        "category": "simple_select",
    },
    # GROUP BY 聚合
    {
        "pattern": "GROUP BY",
        "question_templates": [
            ("统计各地区的客户数量", "SELECT T1.region_name, COUNT(*) FROM regions T1 JOIN customers T2 ON T1.region_id = T2.region_id GROUP BY T1.region_name"),
            ("统计各商品类别的商品数量", "SELECT T1.category_name, COUNT(*) FROM categories T1 JOIN products T2 ON T1.category_id = T2.category_id GROUP BY T1.category_name"),
            ("统计各状态的订单数量", "SELECT status, COUNT(*) FROM orders GROUP BY status"),
            ("统计各支付方式的订单数", "SELECT payment_method, COUNT(*) FROM payments GROUP BY payment_method"),
        ],
        "difficulty": "medium",
        "category": "aggregation",
    },
    # ORDER BY 排序
    {
        "pattern": "ORDER BY",
        "question_templates": [
            ("按年龄从大到小排列所有客户", "SELECT customer_name, age FROM customers ORDER BY age DESC"),
            ("按价格从低到高排列所有商品", "SELECT product_name, price FROM products ORDER BY price ASC"),
            ("按订单金额从高到低排列所有订单", "SELECT order_id, total_amount FROM orders ORDER BY total_amount DESC"),
        ],
        "difficulty": "medium",
        "category": "sorting",
    },
    # WHERE 过滤
    {
        "pattern": "WHERE",
        "question_templates": [
            ("查询年龄大于30岁的客户", "SELECT customer_name, age FROM customers WHERE age > 30"),
            ("查询价格高于100的商品", "SELECT product_name, price FROM products WHERE price > 100"),
            ("查询2024年的订单", "SELECT order_id, order_date, total_amount FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01'"),
            ("查询已完成的订单", "SELECT order_id, total_amount FROM orders WHERE status = 'completed'"),
        ],
        "difficulty": "easy",
        "category": "filtering",
    },
    # JOIN 多表关联
    {
        "pattern": "JOIN",
        "question_templates": [
            ("查询每个客户的订单数量", "SELECT T1.customer_name, COUNT(T2.order_id) FROM customers T1 JOIN orders T2 ON T1.customer_id = T2.customer_id GROUP BY T1.customer_name"),
            ("查询每个地区的销售额", "SELECT T1.region_name, SUM(T3.total_amount) FROM regions T1 JOIN customers T2 ON T1.region_id = T2.region_id JOIN orders T3 ON T2.customer_id = T3.customer_id GROUP BY T1.region_name"),
            ("查询每个商品类别的销售额", "SELECT T1.category_name, SUM(T3.quantity * T3.unit_price) FROM categories T1 JOIN products T2 ON T1.category_id = T2.category_id JOIN order_items T3 ON T2.product_id = T3.product_id GROUP BY T1.category_name"),
            ("查询每个客户的退款总额", "SELECT T1.customer_name, SUM(T3.refund_amount) FROM customers T1 JOIN orders T2 ON T1.customer_id = T2.customer_id JOIN refunds T3 ON T2.order_id = T3.order_id GROUP BY T1.customer_name"),
        ],
        "difficulty": "hard",
        "category": "join",
    },
    # LIMIT 限制
    {
        "pattern": "LIMIT",
        "question_templates": [
            ("查询订单金额最高的前5个订单", "SELECT order_id, total_amount FROM orders ORDER BY total_amount DESC LIMIT 5"),
            ("查询价格最低的前10个商品", "SELECT product_name, price FROM products ORDER BY price ASC LIMIT 10"),
            ("查询年龄最大的前3个客户", "SELECT customer_name, age FROM customers ORDER BY age DESC LIMIT 3"),
        ],
        "difficulty": "medium",
        "category": "limiting",
    },
    # 子查询
    {
        "pattern": "Subquery",
        "question_templates": [
            ("查询年龄大于平均年龄的客户", "SELECT customer_name, age FROM customers WHERE age > (SELECT AVG(age) FROM customers)"),
            ("查询订单金额高于平均金额的订单", "SELECT order_id, total_amount FROM orders WHERE total_amount > (SELECT AVG(total_amount) FROM orders)"),
            ("查询价格高于平均价格的商品", "SELECT product_name, price FROM products WHERE price > (SELECT AVG(price) FROM products)"),
        ],
        "difficulty": "hard",
        "category": "filtering",
    },
    # HAVING
    {
        "pattern": "HAVING",
        "question_templates": [
            ("查询订单数超过5个的客户", "SELECT T1.customer_name, COUNT(T2.order_id) AS order_count FROM customers T1 JOIN orders T2 ON T1.customer_id = T2.customer_id GROUP BY T1.customer_name HAVING COUNT(T2.order_id) > 5"),
            ("查询销售额超过1000的商品类别", "SELECT T1.category_name, SUM(T3.quantity * T3.unit_price) AS total_sales FROM categories T1 JOIN products T2 ON T1.category_id = T2.category_id JOIN order_items T3 ON T2.product_id = T3.product_id GROUP BY T1.category_name HAVING SUM(T3.quantity * T3.unit_price) > 1000"),
        ],
        "difficulty": "hard",
        "category": "aggregation",
    },
    # DISTINCT
    {
        "pattern": "DISTINCT",
        "question_templates": [
            ("查询所有不同的客户性别", "SELECT DISTINCT gender FROM customers"),
            ("查询所有不同的订单状态", "SELECT DISTINCT status FROM orders"),
            ("查询所有不同的支付方式", "SELECT DISTINCT payment_method FROM payments"),
        ],
        "difficulty": "easy",
        "category": "simple_select",
    },
    # BETWEEN
    {
        "pattern": "BETWEEN",
        "question_templates": [
            ("查询年龄在25到35岁之间的客户", "SELECT customer_name, age FROM customers WHERE age BETWEEN 25 AND 35"),
            ("查询价格在50到200之间的商品", "SELECT product_name, price FROM products WHERE price BETWEEN 50 AND 200"),
            ("查询2024年第一季度的订单", "SELECT order_id, order_date, total_amount FROM orders WHERE order_date BETWEEN '2024-01-01' AND '2024-03-31'"),
        ],
        "difficulty": "easy",
        "category": "filtering",
    },
    # LIKE
    {
        "pattern": "LIKE",
        "question_templates": [
            ("查询名字包含'张'的客户", "SELECT customer_name FROM customers WHERE customer_name LIKE '%张%'"),
            ("查询名字以'手机'开头的商品", "SELECT product_name FROM products WHERE product_name LIKE '手机%'"),
        ],
        "difficulty": "easy",
        "category": "filtering",
    },
    # 多表复杂查询
    {
        "pattern": "Complex JOIN",
        "question_templates": [
            ("查询每个地区退款率最高的商品类别", "WITH refund_stats AS (SELECT T1.region_name, T4.category_name, SUM(T5.refund_amount) AS total_refund FROM regions T1 JOIN customers T2 ON T1.region_id = T2.region_id JOIN orders T3 ON T2.customer_id = T3.customer_id JOIN order_items T6 ON T3.order_id = T6.order_id JOIN products T4 ON T6.product_id = T4.product_id JOIN refunds T5 ON T3.order_id = T5.order_id GROUP BY T1.region_name, T4.category_name) SELECT region_name, category_name, total_refund FROM refund_stats ORDER BY region_name, total_refund DESC"),
            ("查询每个客户的消费总额和退款总额", "SELECT T1.customer_name, COALESCE(SUM(T2.total_amount), 0) AS total_spent, COALESCE(SUM(T3.refund_amount), 0) AS total_refund FROM customers T1 LEFT JOIN orders T2 ON T1.customer_id = T2.customer_id LEFT JOIN refunds T3 ON T2.order_id = T3.order_id GROUP BY T1.customer_name"),
        ],
        "difficulty": "extra_hard",
        "category": "join",
    },
]


def classify_spider_difficulty(sql: str) -> str:
    """根据 SQL 复杂度分类难度"""
    sql_upper = sql.upper()
    complexity = 0
    if sql_upper.count("SELECT") > 1:
        complexity += 2
    if "JOIN" in sql_upper:
        complexity += 1
    if "GROUP BY" in sql_upper:
        complexity += 1
    if "HAVING" in sql_upper:
        complexity += 2
    if "UNION" in sql_upper or "EXCEPT" in sql_upper or "INTERSECT" in sql_upper:
        complexity += 2
    if "OVER" in sql_upper:
        complexity += 3
    if "CASE" in sql_upper:
        complexity += 1

    if complexity >= 4:
        return "extra_hard"
    elif complexity >= 2:
        return "hard"
    elif "JOIN" in sql_upper or "GROUP BY" in sql_upper or "ORDER BY" in sql_upper:
        return "medium"
    return "easy"


def classify_spider_category(sql: str) -> str:
    """根据 SQL 特征分类问题类型"""
    sql_upper = sql.upper()
    if "GROUP BY" in sql_upper:
        return "aggregation"
    elif "JOIN" in sql_upper:
        return "join"
    elif "ORDER BY" in sql_upper:
        return "sorting"
    elif "WHERE" in sql_upper:
        return "filtering"
    elif "LIMIT" in sql_upper:
        return "limiting"
    return "simple_select"


def convert_spider_case(spider_case: Dict[str, Any], case_index: int) -> Dict[str, Any]:
    """将单个 Spider case 转换为电商 schema 版本"""
    original_sql = spider_case.get("reference_sql", "").upper()
    difficulty = spider_case.get("difficulty", classify_spider_difficulty(spider_case.get("reference_sql", "")))
    category = spider_case.get("category", classify_spider_category(spider_case.get("reference_sql", "")))

    # 根据原始 SQL 模式选择合适的映射
    selected_template = None

    # 优先匹配复杂模式
    if "JOIN" in original_sql and ("GROUP BY" in original_sql or "HAVING" in original_sql):
        for rule in MAPPING_RULES:
            if rule["pattern"] == "Complex JOIN":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "HAVING" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "HAVING":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "JOIN" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "JOIN":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "GROUP BY" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "GROUP BY":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "ORDER BY" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "ORDER BY":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "WHERE" in original_sql and ("BETWEEN" in original_sql or "LIKE" in original_sql):
        pattern = "BETWEEN" if "BETWEEN" in original_sql else "LIKE"
        for rule in MAPPING_RULES:
            if rule["pattern"] == pattern:
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "WHERE" in original_sql:
        # 检查是否是子查询
        if original_sql.count("SELECT") > 1:
            for rule in MAPPING_RULES:
                if rule["pattern"] == "Subquery":
                    selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                    break
        else:
            for rule in MAPPING_RULES:
                if rule["pattern"] == "WHERE":
                    selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                    break
    elif "DISTINCT" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "DISTINCT":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "LIMIT" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "LIMIT":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "AVG" in original_sql or "MAX" in original_sql or "MIN" in original_sql:
        pattern = "AVG" if "AVG" in original_sql else ("MAX" if "MAX" in original_sql else "MIN")
        for rule in MAPPING_RULES:
            if rule["pattern"] == pattern:
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break
    elif "COUNT" in original_sql:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "COUNT(*)":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break

    # 默认使用简单计数
    if not selected_template:
        for rule in MAPPING_RULES:
            if rule["pattern"] == "COUNT(*)":
                selected_template = rule["question_templates"][case_index % len(rule["question_templates"])]
                break

    question, reference_sql = selected_template

    # 提取使用的表
    tables_used = []
    for table_name in ECOMMERCE_SCHEMA:
        if table_name.lower() in reference_sql.lower():
            tables_used.append(table_name)

    return {
        "id": f"ecommerce_spider_{case_index:03d}",
        "question": question,
        "category": category,
        "difficulty": difficulty,
        "safety_expected": "safe",
        "expected_tables": tables_used,
        "reference_sql": reference_sql,
        "source": "spider_converted",
        "original_db_id": spider_case.get("db_id", ""),
        "original_question": spider_case.get("question", ""),
    }


def convert_all_cases(max_cases: int = 200) -> List[Dict[str, Any]]:
    """转换所有 Spider case"""
    with open(SPIDER_CASES_FILE, "r", encoding="utf-8") as f:
        spider_data = yaml.safe_load(f)

    spider_cases = spider_data["cases"][:max_cases]
    converted_cases = []

    for i, spider_case in enumerate(spider_cases):
        converted = convert_spider_case(spider_case, i)
        converted_cases.append(converted)

    return converted_cases


def save_converted_cases(cases: List[Dict[str, Any]]):
    """保存转换后的 case"""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump({"cases": cases}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"转换完成: {len(cases)} 条 case")
    print(f"已保存到: {OUTPUT_FILE}")


if __name__ == "__main__":
    cases = convert_all_cases(max_cases=200)
    save_converted_cases(cases)

    # 打印统计
    stats = {}
    for c in cases:
        d = c["difficulty"]
        stats[d] = stats.get(d, 0) + 1
    print(f"难度分布: {stats}")

    category_stats = {}
    for c in cases:
        cat = c["category"]
        category_stats[cat] = category_stats.get(cat, 0) + 1
    print(f"类别分布: {category_stats}")
