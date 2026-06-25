# 查询缓存模块
# 基于问题文本的精确匹配缓存，避免相同问题重复调用 LLM

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings
from ..utils.logger import logger


class QueryCache:
    """查询结果缓存

    对相同问题返回缓存结果，避免重复调用 LLM 和数据库。
    缓存存储在 SQLite 中，支持 TTL 过期和容量限制。
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        ttl_seconds: int = 3600,       # 缓存 1 小时过期
        max_entries: int = 1000,        # 最多缓存 1000 条
    ):
        self._db_path = db_path or str(settings.DATA_DIR / "query_cache.db")
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._local = threading.local()
        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化：首次使用时才创建数据库"""
        if self._initialized:
            return
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True

    def _get_conn(self) -> sqlite3.Connection:
        self._ensure_initialized()
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, timeout=10)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_key TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _make_key(self, question: str, session_id: Optional[str] = None) -> str:
        """生成缓存键：问题文本的 SHA256 哈希（不含 session_id，相同问题跨会话命中）"""
        normalized = question.strip().casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    def get(self, question: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """查询缓存，返回命中结果或 None"""
        key = self._make_key(question, session_id)
        conn = self._get_conn()

        row = conn.execute(
            "SELECT result_json, created_at, hit_count FROM query_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()

        if not row:
            return None

        result_json, created_at, hit_count = row

        # 检查是否过期
        if time.time() - created_at > self._ttl:
            conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
            conn.commit()
            return None

        # 更新命中计数
        conn.execute(
            "UPDATE query_cache SET hit_count = ? WHERE cache_key = ?",
            (hit_count + 1, key),
        )
        conn.commit()

        logger.info(f"缓存命中: {question[:50]}... (命中 {hit_count + 1} 次)")
        return json.loads(result_json)

    def put(self, question: str, result: Dict[str, Any], session_id: Optional[str] = None) -> None:
        """将结果写入缓存"""
        key = self._make_key(question, session_id)
        conn = self._get_conn()

        conn.execute(
            """
            INSERT OR REPLACE INTO query_cache (cache_key, question, result_json, created_at, hit_count)
            VALUES (?, ?, ?, ?, 0)
            """,
            (key, question.strip(), json.dumps(result, ensure_ascii=False), time.time()),
        )

        # 淘汰最旧的条目
        conn.execute(
            """
            DELETE FROM query_cache WHERE cache_key NOT IN (
                SELECT cache_key FROM query_cache ORDER BY created_at DESC LIMIT ?
            )
            """,
            (self._max_entries,),
        )
        conn.commit()

    def invalidate(self, question: str) -> None:
        """手动失效某条缓存"""
        key = self._make_key(question)
        conn = self._get_conn()
        conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
        conn.commit()

    def clear(self) -> None:
        """清空所有缓存"""
        conn = self._get_conn()
        conn.execute("DELETE FROM query_cache")
        conn.commit()

    def stats(self) -> Dict[str, Any]:
        """返回缓存统计"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*), SUM(hit_count) FROM query_cache"
        ).fetchone()
        return {
            "entries": row[0] or 0,
            "total_hits": row[1] or 0,
        }


# 全局缓存实例
query_cache = QueryCache()
