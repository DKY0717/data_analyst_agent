# 数据库连接管理模块
# 提供DuckDB数据库连接的创建、管理和会话控制
# 每次 get_session() 创建独立连接，避免并发请求共享同一连接导致数据竞争

import duckdb
from contextlib import contextmanager
from pathlib import Path

from ..config import settings
from ..utils.logger import logger
from ..utils.exceptions import DatabaseError

class DatabaseConnection:
    """数据库连接管理器（连接工厂模式，每次会话创建独立连接）"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接管理器

        Args:
            db_path: 数据库文件路径，默认使用配置中的数据目录
        """
        self.db_path = db_path or str(settings.DATA_DIR / "database.duckdb")

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        创建新的数据库连接（每次调用返回独立连接）

        Returns:
            DuckDB数据库连接对象

        Raises:
            DatabaseError: 连接失败时抛出异常
        """
        try:
            conn = duckdb.connect(self.db_path)
            return conn
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            raise DatabaseError(f"连接数据库失败: {e}")

    @contextmanager
    def get_session(self):
        """
        获取数据库会话（上下文管理器，自动创建和关闭连接）

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
        finally:
            conn.close()

# 全局数据库连接实例
db_connection = DatabaseConnection()

def get_db():
    """
    FastAPI依赖注入函数

    Returns:
        数据库会话上下文管理器
    """
    return db_connection.get_session()