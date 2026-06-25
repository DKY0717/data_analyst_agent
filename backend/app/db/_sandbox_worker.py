# 沙箱 Worker 脚本
# 在子进程中运行，通过 stdin 接收 SQL，通过 stdout 返回结果
# 此脚本不应被主进程直接 import，只通过 subprocess 调用

import json
import sys
import time


def main():
    # 从 stdin 读取输入
    input_data = json.loads(sys.stdin.read())
    sql = input_data["sql"]
    db_path = input_data["db_path"]
    backend = input_data["backend"]

    start_time = time.time()

    try:
        if backend == "postgresql":
            import psycopg2
            conn = psycopg2.connect(db_path)
            cur = conn.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [list(row) for row in cur.fetchall()]
            conn.close()
        else:
            import duckdb
            conn = duckdb.connect(db_path, read_only=True)
            result = conn.execute(sql)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = [list(row) for row in result.fetchall()]
            conn.close()

        execution_time_ms = int((time.time() - start_time) * 1000)

        output = {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False))

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        output = {
            "success": False,
            "columns": [],
            "rows": [],
            "error": str(e),
            "error_type": type(e).__name__,
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
