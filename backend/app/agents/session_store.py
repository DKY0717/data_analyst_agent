# SQLite 持久化会话存储
# 替代内存版 SessionStore，重启后会话不丢失

import json
import sqlite3
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from ..config import settings
from ..utils.logger import logger
from .conversation_context import conversation_context_builder, ConversationContextBuilder


class SQLiteSessionStore:
    """基于 SQLite 的会话持久化存储

    与内存版 SessionStore 接口完全兼容，可无缝替换。
    会话数据存储在 data/sessions.db 中，重启后自动恢复。
    """

    def __init__(
        self,
        max_turns: int = 3,
        context_builder: ConversationContextBuilder = conversation_context_builder,
        db_path: Optional[str] = None,
    ):
        self.max_turns = max_turns
        self.context_builder = context_builder
        self._db_path = db_path or str(settings.DATA_DIR / "sessions.db")
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
        """每个线程独立连接，避免并发写入冲突"""
        self._ensure_initialized()
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, timeout=10)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS session_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_session_turns_session_id
                    ON session_turns(session_id);

                CREATE TABLE IF NOT EXISTS pending_clarifications (
                    session_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    clarification_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def append_turn(self, session_id: Optional[str], final_state: Dict[str, Any]) -> None:
        """保存一轮结果到 SQLite"""
        if not session_id:
            return

        if final_state.get("intent_is_safe", True) is False:
            return

        if not final_state.get("is_sql_safe"):
            return

        if not final_state.get("execution_success"):
            turn_data = self.context_builder.extract_failed_turn(final_state)
        else:
            turn_data = self.context_builder.extract_turn(final_state)

        conn = self._get_conn()
        conn.execute(
            "INSERT INTO session_turns (session_id, turn_data) VALUES (?, ?)",
            (session_id, json.dumps(turn_data, ensure_ascii=False)),
        )

        # 只保留最近 max_turns 轮
        conn.execute(
            """
            DELETE FROM session_turns WHERE session_id = ? AND id NOT IN (
                SELECT id FROM session_turns WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
            )
            """,
            (session_id, session_id, self.max_turns),
        )
        conn.commit()

    def get_context(self, session_id: Optional[str]) -> str:
        """返回该 session 最近几轮的 prompt 上下文"""
        if not session_id:
            return ""

        conn = self._get_conn()
        rows = conn.execute(
            "SELECT turn_data FROM session_turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, self.max_turns),
        ).fetchall()

        if not rows:
            return ""

        turns = [json.loads(row[0]) for row in reversed(rows)]
        return self.context_builder.build_context(turns)

    def save_pending_clarification(
        self,
        session_id: Optional[str],
        question: str,
        clarification: Dict[str, Any],
    ) -> None:
        """保存等待用户选择的澄清请求"""
        if not session_id:
            return

        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_clarifications (session_id, question, clarification_data)
            VALUES (?, ?, ?)
            """,
            (session_id, question, json.dumps(clarification, ensure_ascii=False)),
        )
        conn.commit()

    def resolve_pending_clarification(
        self,
        session_id: Optional[str],
        clarification_id: str,
        *,
        candidate_id: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """按稳定候选 ID 或自由文本恢复原问题"""
        if not session_id:
            return None

        conn = self._get_conn()
        row = conn.execute(
            "SELECT question, clarification_data FROM pending_clarifications WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return None

        original_question = row[0]
        clarification = json.loads(row[1])

        if clarification.get("clarification_id") != clarification_id:
            return None

        option = self._match_clarification_option(
            clarification.get("options", []),
            candidate_id,
            text,
        )
        if option is None:
            return None

        # 消费 pending 请求
        conn.execute(
            "DELETE FROM pending_clarifications WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()

        selected_label = option["label"]
        selected_id = option["candidate_id"]
        return {
            "original_question": original_question,
            "candidate_id": selected_id,
            "label": selected_label,
            "resolved_question": f"{original_question}。用户澄清：{selected_label}（{selected_id}）",
        }

    @staticmethod
    def _match_clarification_option(
        options: list[Dict[str, Any]],
        candidate_id: Optional[str],
        text: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """自由文本也必须归一化到已有候选"""
        normalized_text = (text or "").strip().casefold()
        for option in options:
            if candidate_id and option.get("candidate_id") == candidate_id:
                return option
            labels = [
                option.get("label", ""),
                option.get("description", ""),
                option.get("candidate_id", ""),
            ]
            if normalized_text and any(
                normalized_text == str(label).strip().casefold()
                for label in labels
            ):
                return option
        return None

    def clear(self, session_id: Optional[str] = None) -> None:
        """清理历史"""
        conn = self._get_conn()
        if session_id:
            conn.execute("DELETE FROM session_turns WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM pending_clarifications WHERE session_id = ?", (session_id,))
        else:
            conn.execute("DELETE FROM session_turns")
            conn.execute("DELETE FROM pending_clarifications")
        conn.commit()

    def close(self) -> None:
        """关闭当前线程连接，便于隔离评测可靠清理临时目录。"""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# 全局实例（替换内存版 session_store）
session_store = SQLiteSessionStore()
