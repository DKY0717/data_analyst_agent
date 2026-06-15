# Schema加载器模块
# 从数据库中读取表结构信息，供SQL生成器使用

import re
from typing import Dict, List, Any

from ..db.connection import db_connection
from ..utils.logger import logger
from ..utils.exceptions import SchemaLoadError

class SchemaLoader:
    """数据库Schema加载器"""

    def __init__(self):
        """初始化Schema加载器"""
        self.db = db_connection

    def get_tables(self) -> List[str]:
        """
        获取数据库中所有表名

        Returns:
            表名列表

        Raises:
            SchemaLoadError: 获取表列表失败时抛出异常
        """
        try:
            with self.db.get_session() as conn:
                # 查询information_schema获取所有表
                result = conn.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main'
                    ORDER BY table_name
                """).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            raise SchemaLoadError(f"获取表列表失败: {e}")

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        获取指定表的结构信息

        Args:
            table_name: 表名

        Returns:
            包含表结构信息的字典，包括列信息和主键信息

        Raises:
            SchemaLoadError: 获取表结构失败时抛出异常
        """
        try:
            with self.db.get_session() as conn:
                # 获取列信息
                columns = conn.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'main'
                    AND table_name = ?
                    ORDER BY ordinal_position
                """, [table_name]).fetchall()

                # DuckDB 0.9 尚未暴露标准 table_constraints，统一从约束目录读取主外键。
                constraints = conn.execute("""
                    SELECT constraint_type, constraint_text, constraint_column_names
                    FROM duckdb_constraints()
                    WHERE schema_name = 'main'
                    AND table_name = ?
                    ORDER BY constraint_index
                """, [table_name]).fetchall()
                primary_keys, foreign_keys = self._parse_constraints(constraints)

                return {
                    "table_name": table_name,
                    "columns": [
                        {
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES"
                        }
                        for col in columns
                    ],
                    "primary_keys": primary_keys,
                    "foreign_keys": foreign_keys,
                }
        except Exception as e:
            logger.error(f"获取表 {table_name} 结构失败: {e}")
            raise SchemaLoadError(f"获取表 {table_name} 结构失败: {e}")

    def get_full_schema(self) -> Dict[str, Any]:
        """
        获取完整的数据库Schema

        Returns:
            包含所有表结构的字典

        Raises:
            SchemaLoadError: 获取完整Schema失败时抛出异常
        """
        try:
            tables = self.get_tables()
            schema = {}

            for table in tables:
                schema[table] = self.get_table_schema(table)

            return {"tables": schema}
        except Exception as e:
            logger.error(f"获取完整Schema失败: {e}")
            raise SchemaLoadError(f"获取完整Schema失败: {e}")

    @staticmethod
    def _parse_constraints(constraints: List[tuple]) -> tuple[List[str], List[Dict[str, str]]]:
        """将 DuckDB 约束目录转换为下游路由可直接使用的稳定结构。"""
        primary_keys: List[str] = []
        foreign_keys: List[Dict[str, str]] = []

        for constraint_type, constraint_text, column_names in constraints:
            local_columns = list(column_names or [])
            if constraint_type == "PRIMARY KEY":
                primary_keys.extend(local_columns)
                continue
            if constraint_type != "FOREIGN KEY":
                continue

            # DuckDB 0.9 只结构化返回本地列，引用表与列需从固定约束文本中提取。
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

# 全局Schema加载器实例
schema_loader = SchemaLoader()
