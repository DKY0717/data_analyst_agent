# Spider 数据集转换器
# 将 Spider dev.json 转换为项目评测格式

import json
import yaml
from pathlib import Path


SPIDER_DIR = Path(__file__).parent.parent.parent / "data" / "spider"
OUTPUT_DIR = Path(__file__).parent / "cases"


def load_spider_data():
    """加载 Spider 数据"""
    with open(SPIDER_DIR / "dev.json", "r", encoding="utf-8") as f:
        cases = json.load(f)
    with open(SPIDER_DIR / "tables.json", "r", encoding="utf-8") as f:
        tables = json.load(f)
    return cases, tables


def get_db_tables_map(tables):
    """构建 db_id -> tables 映射"""
    return {t["db_id"]: t for t in tables}


def classify_difficulty(sql: str) -> str:
    """根据 SQL 复杂度分类难度"""
    sql_upper = sql.upper()

    has_subquery = "SELECT" in sql_upper and sql_upper.count("SELECT") > 1
    has_join = "JOIN" in sql_upper
    has_group = "GROUP BY" in sql_upper
    has_having = "HAVING" in sql_upper
    has_order = "ORDER BY" in sql_upper
    has_union = "UNION" in sql_upper
    has_except = "EXCEPT" in sql_upper
    has_intersect = "INTERSECT" in sql_upper
    has_window = "OVER" in sql_upper
    has_case = "CASE" in sql_upper

    complexity = sum([
        has_subquery * 2,
        has_join * 1,
        has_group * 1,
        has_having * 2,
        has_union * 2,
        has_except * 2,
        has_intersect * 2,
        has_window * 3,
        has_case * 1,
    ])

    if complexity >= 4:
        return "extra_hard"
    elif complexity >= 2:
        return "hard"
    elif has_join or has_group or has_order:
        return "medium"
    else:
        return "easy"


def classify_category(sql: str) -> str:
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
    else:
        return "simple_select"


def get_tables_from_sql(sql: str, db_schema: dict) -> list:
    """从 SQL 中提取使用的表名"""
    sql_lower = sql.lower()
    tables = []
    for table_name in db_schema.get("table_names_original", []):
        if table_name.lower() in sql_lower:
            tables.append(table_name)
    return tables


def convert_case(spider_case: dict, db_schema: dict) -> dict:
    """转换单个 Spider case 为项目格式"""
    sql = spider_case["query"]
    question = spider_case["question"]
    db_id = spider_case["db_id"]

    difficulty = classify_difficulty(sql)
    category = classify_category(sql)
    tables_used = get_tables_from_sql(sql, db_schema)

    return {
        "id": f"spider_{db_id}_{spider_case.get('question_toks', [''])[0].lower()}",
        "question": question,
        "db_id": db_id,
        "category": category,
        "difficulty": difficulty,
        "safety_expected": "safe",
        "expected_tables": tables_used,
        "reference_sql": sql,
        "source": "spider",
    }


def convert_spider_to_yaml(max_cases: int = 200):
    """转换 Spider 数据为项目评测格式"""
    cases, tables = load_spider_data()
    db_map = get_db_tables_map(tables)

    converted = []
    for case in cases:
        db_id = case["db_id"]
        if db_id not in db_map:
            continue

        db_schema = db_map[db_id]
        converted_case = convert_case(case, db_schema)
        converted.append(converted_case)

        if len(converted) >= max_cases:
            break

    # 按难度分组统计
    stats = {}
    for c in converted:
        d = c["difficulty"]
        stats[d] = stats.get(d, 0) + 1

    print(f"转换完成: {len(converted)} 条用例")
    print(f"难度分布: {stats}")

    # 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "spider_nl2sql_cases.yaml"
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump({"cases": converted}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"已保存: {output_path}")
    return converted


if __name__ == "__main__":
    convert_spider_to_yaml(max_cases=200)
