# Schema加载器模块
# 从数据库中读取表结构信息，供SQL生成器使用

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
                columns = conn.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """).fetchall()

                # 获取主键信息（使用DuckDB兼容的方式）
                # DuckDB使用pg_constraint系统表
                primary_keys = []
                try:
                    pk_result = conn.execute(f"""
                        SELECT column_name
                        FROM information_schema.key_column_usage
                        WHERE table_name = '{table_name}'
                        AND constraint_name LIKE '%_pkey'
                    """).fetchall()
                    primary_keys = [pk[0] for pk in pk_result]
                except Exception:
                    # 如果查询失败，返回空列表
                    pass

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
                    "primary_keys": primary_keys
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

# 全局Schema加载器实例
schema_loader = SchemaLoader()