# Prompt 版本管理模块
# 存储和追踪所有 LLM prompt 的版本，支持回滚和对比

import json
import hashlib
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from ..utils.logger import logger


class PromptVersion:
    """单个 prompt 版本"""

    def __init__(
        self,
        name: str,
        version: int,
        system_prompt: str,
        user_template: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.version = version
        self.system_prompt = system_prompt
        self.user_template = user_template
        self.metadata = metadata or {}
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        content = f"{self.system_prompt}|{self.user_template}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class PromptRegistry:
    """Prompt 版本注册表

    功能：
    - 注册 prompt 模板，自动版本递增
    - 记录每次变更的 hash 和时间
    - 支持按名称获取最新版本
    - 支持按版本号回滚
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(settings.DATA_DIR / "prompts.db")
        self._local = threading.local()
        self._initialized = False
        self._cache: Dict[str, PromptVersion] = {}

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
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    system_prompt TEXT NOT NULL,
                    user_template TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, version)
                );

                CREATE INDEX IF NOT EXISTS idx_prompt_name
                    ON prompt_versions(name);
            """)
            conn.commit()
        finally:
            conn.close()

    def register(
        self,
        name: str,
        system_prompt: str,
        user_template: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        """注册或更新 prompt 模板

        如果内容与最新版本相同，不创建新版本。
        """
        conn = self._get_conn()

        # 获取最新版本
        row = conn.execute(
            "SELECT version, system_prompt, user_template FROM prompt_versions WHERE name = ? ORDER BY version DESC LIMIT 1",
            (name,),
        ).fetchone()

        if row:
            latest_version, latest_system, latest_user = row
            # 内容没变就不创建新版本
            if latest_system == system_prompt and latest_user == user_template:
                version = PromptVersion(name, latest_version, system_prompt, user_template, metadata)
                self._cache[name] = version
                return version
            new_version = latest_version + 1
        else:
            new_version = 1

        version = PromptVersion(name, new_version, system_prompt, user_template, metadata)

        conn.execute(
            """
            INSERT INTO prompt_versions (name, version, system_prompt, user_template, hash, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, new_version, system_prompt, user_template, version.hash, json.dumps(metadata or {})),
        )
        conn.commit()

        self._cache[name] = version
        logger.info(f"Prompt '{name}' 注册版本 v{new_version} (hash: {version.hash})")
        return version

    def get_latest(self, name: str) -> Optional[PromptVersion]:
        """获取指定名称的最新 prompt 版本"""
        if name in self._cache:
            return self._cache[name]

        conn = self._get_conn()
        row = conn.execute(
            "SELECT version, system_prompt, user_template, metadata FROM prompt_versions WHERE name = ? ORDER BY version DESC LIMIT 1",
            (name,),
        ).fetchone()

        if not row:
            return None

        version, system_prompt, user_template, metadata_str = row
        pv = PromptVersion(name, version, system_prompt, user_template, json.loads(metadata_str))
        self._cache[name] = pv
        return pv

    def get_by_version(self, name: str, version: int) -> Optional[PromptVersion]:
        """按版本号获取指定 prompt"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT system_prompt, user_template, metadata FROM prompt_versions WHERE name = ? AND version = ?",
            (name, version),
        ).fetchone()

        if not row:
            return None

        system_prompt, user_template, metadata_str = row
        return PromptVersion(name, version, system_prompt, user_template, json.loads(metadata_str))

    def list_versions(self, name: str) -> List[Dict[str, Any]]:
        """列出指定 prompt 的所有版本"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT version, hash, created_at FROM prompt_versions WHERE name = ? ORDER BY version",
            (name,),
        ).fetchall()

        return [
            {"version": row[0], "hash": row[1], "created_at": row[2]}
            for row in rows
        ]

    def rollback(self, name: str, target_version: int) -> Optional[PromptVersion]:
        """回滚到指定版本（创建一个新版本，内容复制自目标版本）"""
        target = self.get_by_version(name, target_version)
        if not target:
            return None

        return self.register(
            name=name,
            system_prompt=target.system_prompt,
            user_template=target.user_template,
            metadata={"rollback_from": target_version},
        )


# 全局注册表
prompt_registry = PromptRegistry()
