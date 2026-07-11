# 沙箱 Worker 脚本
# 在子进程中运行，通过 stdin 接收 SQL，通过 stdout 返回结果
# 此脚本不应被主进程直接 import，只通过 subprocess 调用

import json
import sys
from datetime import date, datetime
from decimal import Decimal


def _json_default(value):
    """把数据库标量转换为稳定 JSON 类型，未知对象继续 fail-closed。"""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Unsupported database value type: {type(value).__name__}")


def main():
    # 从 stdin 读取输入
    input_data = json.loads(sys.stdin.read())
    sql = input_data["sql"]
    connection_config = input_data.get("connection_config", input_data.get("db_path"))
    backend = input_data["backend"]
    timeout = int(input_data.get("timeout") or 30)

    try:
        if backend == "postgresql":
            import psycopg2
            conn = psycopg2.connect(**connection_config)
            cur = conn.cursor()
            # 服务端事务级超时和父进程强杀共同构成双层边界。
            cur.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{timeout}s",),
            )
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [list(row) for row in cur.fetchall()]
            conn.close()
        else:
            import duckdb
            conn = duckdb.connect(connection_config, read_only=True)
            result = conn.execute(sql)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = [list(row) for row in result.fetchall()]
            conn.close()

        output = {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False, default=_json_default))

    except Exception as e:
        output = {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
            "error_type": type(e).__name__,
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False, default=_json_default))


if __name__ == "__main__":
    main()
