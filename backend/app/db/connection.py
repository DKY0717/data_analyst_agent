# 数据库连接管理模块
# 提供DuckDB数据库连接的创建、管理和会话控制

import duckdb
from contextlib import contextmanager
from pathlib import Path

from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import DatabaseError

class DatabaseConnection:
    """数据库连接管理器"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接管理器

        Args:
            db_path: 数据库文件路径，默认使用配置中的数据目录
        """
        self.db_path = db_path or str(settings.DATA_DIR / "database.duckdb")
        self._connection = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        获取数据库连接

        Returns:
            DuckDB数据库连接对象

        Raises:
            DatabaseError: 连接失败时抛出异常
        """
        # 如果连接不存在，则创建新连接
        if self._connection is None:
            try:
                self._connection = duckdb.connect(self.db_path)
                logger.info(f"已连接到数据库: {self.db_path}")
            except Exception as e:
                logger.error(f"连接数据库失败: {e}")
                raise DatabaseError(f"连接数据库失败: {e}")
        return self._connection

    def close(self):
        """关闭数据库连接"""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接时出错: {e}")

    @contextmanager
    def get_session(self):
        """
        获取数据库会话（上下文管理器）

        Yields:
            数据库连接对象

        Raises:
            DatabaseError: 会话操作出错时抛出异常
        """
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            raise DatabaseError(f"数据库会话错误: {e}")

# 全局数据库连接实例
db_connection = DatabaseConnection()

def get_db():
    """
    FastAPI依赖注入函数

    Returns:
        数据库会话上下文管理器
    """
    return db_connection.get_session()