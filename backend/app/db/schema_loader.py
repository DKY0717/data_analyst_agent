# Schema加载器模块
# 支持 DuckDB 和 PostgreSQL 双后端，自动适配方言差异

import re
from typing import Dict, List, Any

from ..db.connection import db_connection
from ..utils.logger import logger
from ..utils.exceptions import SchemaLoadError


class SchemaLoader:
    """数据库Schema加载器（双后端支持）"""

    def __init__(self, db=None):
        # Core-path 等确定性评测可注入隔离连接；生产使用全局数据库连接。
        self._db = db

    @property
    def db(self):
        """未注入时动态读取全局连接，保留运行时后端切换和测试替换能力。"""
        return self._db or db_connection

    @property
    def _is_pg(self) -> bool:
        return self.db.backend == "postgresql"

    @property
    def _schema_name(self) -> str:
        return "public" if self._is_pg else "main"

    @property
    def _placeholder(self) -> str:
        return "%s" if self._is_pg else "?"

    def get_tables(self) -> List[str]:
        """获取数据库中所有表名"""
        try:
            with self.db.get_session() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT table_name FROM information_schema.tables "
                    f"WHERE table_schema = '{self._schema_name}' "
                    f"ORDER BY table_name"
                )
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error("获取表列表失败: %s", type(e).__name__)
            raise SchemaLoadError("获取表列表失败") from e

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """获取指定表的结构信息"""
        try:
            with self.db.get_session() as conn:
                cur = conn.cursor()
                ph = self._placeholder

                # 获取列信息
                cur.execute(
                    f"SELECT column_name, data_type, is_nullable "
                    f"FROM information_schema.columns "
                    f"WHERE table_schema = '{self._schema_name}' "
                    f"AND table_name = {ph} "
                    f"ORDER BY ordinal_position",
                    [table_name],
                )
                columns = cur.fetchall()

                # 获取主键和外键
                if self._is_pg:
                    primary_keys, foreign_keys = self._get_pg_constraints(conn, table_name)
                else:
                    primary_keys, foreign_keys = self._get_duckdb_constraints(conn, table_name)

                return {
                    "table_name": table_name,
                    "columns": [
                        {
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES",
                        }
                        for col in columns
                    ],
                    "primary_keys": primary_keys,
                    "foreign_keys": foreign_keys,
                }
        except Exception as e:
            logger.error("获取表结构失败: %s", type(e).__name__)
            raise SchemaLoadError("获取表结构失败") from e

    def _get_pg_constraints(self, conn, table_name: str) -> tuple:
        """PostgreSQL 约束查询"""
        cur = conn.cursor()

        # 主键
        cur.execute(
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.table_schema = 'public' "
            "AND tc.table_name = %s "
            "AND tc.constraint_type = 'PRIMARY KEY'",
            [table_name],
        )
        primary_keys = [row[0] for row in cur.fetchall()]

        # 外键
        cur.execute(
            "SELECT kcu.column_name, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.table_schema = 'public' "
            "AND tc.table_name = %s "
            "AND tc.constraint_type = 'FOREIGN KEY'",
            [table_name],
        )
        foreign_keys = [
            {
                "column": row[0],
                "referenced_table": row[1],
                "referenced_column": row[2],
            }
            for row in cur.fetchall()
        ]

        return primary_keys, foreign_keys

    def _get_duckdb_constraints(self, conn, table_name: str) -> tuple:
        """DuckDB 约束查询"""
        cur = conn.cursor()
        cur.execute(
            "SELECT constraint_type, constraint_text, constraint_column_names "
            "FROM duckdb_constraints() "
            "WHERE schema_name = 'main' "
            "AND table_name = ? "
            "ORDER BY constraint_index",
            [table_name],
        )
        constraints = cur.fetchall()
        return self._parse_constraints(constraints)

    def get_full_schema(self) -> Dict[str, Any]:
        """获取完整的数据库Schema"""
        try:
            tables = self.get_tables()
            schema = {}
            for table in tables:
                schema[table] = self.get_table_schema(table)
            return {"tables": schema}
        except Exception as e:
            logger.error("获取完整 Schema 失败: %s", type(e).__name__)
            raise SchemaLoadError("获取完整 Schema 失败") from e

    @staticmethod
    def _parse_constraints(constraints: List[tuple]) -> tuple:
        """DuckDB 约束解析"""
        primary_keys: List[str] = []
        foreign_keys: List[Dict[str, str]] = []

        for constraint_type, constraint_text, column_names in constraints:
            local_columns = list(column_names or [])
            if constraint_type == "PRIMARY KEY":
                primary_keys.extend(local_columns)
                continue
            if constraint_type != "FOREIGN KEY":
                continue

            match = re.search(
                r"REFERENCES\s+(?:[\w\"]+\.)?([\w\"]+)\s*\(([^)]+)\)",
                constraint_text or "",
                re.IGNORECASE,
            )
            if not match:
                continue
            referenced_table = match.group(1).strip('"')
            referenced_columns = [
                column.strip().strip('"') for column in match.group(2).split(",")
            ]
            for local_column, referenced_column in zip(
                local_columns, referenced_columns
            ):
                foreign_keys.append(
                    {
                        "column": local_column,
                        "referenced_table": referenced_table,
                        "referenced_column": referenced_column,
                    }
                )

        return primary_keys, foreign_keys


schema_loader = SchemaLoader()
