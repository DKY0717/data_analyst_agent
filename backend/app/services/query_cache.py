# 查询缓存模块
# 支持精确匹配和语义相似匹配，避免相同/相似问题重复调用 LLM

import hashlib
import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..config import settings
from ..utils.logger import logger


def _tokenize(text: str) -> Set[str]:
    """中文分词 + 英文分词（简易版，不依赖外部库）"""
    text = text.strip().casefold()
    # 中文：按字分
    chinese_chars = set(re.findall(r'[\u4e00-\u9fff]', text))
    # 英文/数字：按词分
    words = set(re.findall(r'[a-z0-9]+', text))
    return chinese_chars | words


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Jaccard 相似度"""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


class QueryCache:
    """查询结果缓存

    支持两种匹配模式：
    1. 精确匹配：问题文本完全相同（SHA256 哈希）
    2. 语义相似匹配：基于 Jaccard 相似度，阈值 0.85
    """

    SIMILARITY_THRESHOLD = 0.85

    def __init__(
        self,
        db_path: Optional[str] = None,
        ttl_seconds: int = 3600,
        max_entries: int = 1000,
    ):
        self._db_path = db_path or str(settings.DATA_DIR / "query_cache.db")
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._local = threading.local()
        self._initialized = False

    def _ensure_initialized(self):
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
                    question_tokens TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _make_key(self, question: str) -> str:
        normalized = question.strip().casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]

    def get(self, question: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """查询缓存，支持精确匹配和语义相似匹配"""
        key = self._make_key(question)
        conn = self._get_conn()

        # 1. 精确匹配
        row = conn.execute(
            "SELECT result_json, created_at, hit_count FROM query_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()

        if row:
            result_json, created_at, hit_count = row
            if time.time() - created_at <= self._ttl:
                conn.execute(
                    "UPDATE query_cache SET hit_count = ? WHERE cache_key = ?",
                    (hit_count + 1, key),
                )
                conn.commit()
                logger.info(f"缓存精确命中: {question[:50]}...")
                return json.loads(result_json)
            else:
                conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
                conn.commit()

        # 2. 语义相似匹配
        query_tokens = _tokenize(question)
        if not query_tokens:
            return None

        rows = conn.execute(
            "SELECT cache_key, question_tokens, result_json, created_at, hit_count FROM query_cache"
        ).fetchall()

        best_match = None
        best_similarity = 0.0

        for row_key, tokens_json, result_json, created_at, hit_count in rows:
            # 跳过过期
            if time.time() - created_at > self._ttl:
                continue

            cached_tokens = set(json.loads(tokens_json))
            similarity = _jaccard_similarity(query_tokens, cached_tokens)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = (row_key, result_json, hit_count)

        if best_match and best_similarity >= self.SIMILARITY_THRESHOLD:
            row_key, result_json, hit_count = best_match
            conn.execute(
                "UPDATE query_cache SET hit_count = ? WHERE cache_key = ?",
                (hit_count + 1, row_key),
            )
            conn.commit()
            logger.info(f"缓存语义命中 (相似度 {best_similarity:.2f}): {question[:50]}...")
            return json.loads(result_json)

        return None

    def put(self, question: str, result: Dict[str, Any], session_id: Optional[str] = None) -> None:
        """将结果写入缓存"""
        key = self._make_key(question)
        tokens = list(_tokenize(question))
        conn = self._get_conn()

        conn.execute(
            """
            INSERT OR REPLACE INTO query_cache (cache_key, question, question_tokens, result_json, created_at, hit_count)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (key, question.strip(), json.dumps(tokens, ensure_ascii=False), json.dumps(result, ensure_ascii=False), time.time()),
        )

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
        key = self._make_key(question)
        conn = self._get_conn()
        conn.execute("DELETE FROM query_cache WHERE cache_key = ?", (key,))
        conn.commit()

    def clear(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM query_cache")
        conn.commit()

    def stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*), SUM(hit_count) FROM query_cache"
        ).fetchone()
        return {
            "entries": row[0] or 0,
            "total_hits": row[1] or 0,
        }


query_cache = QueryCache()
