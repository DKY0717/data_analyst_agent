# Prompt A/B 测试框架
# 支持同时运行多个 prompt 版本，自动收集指标并对比效果

import hashlib
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from ..utils.logger import logger


@dataclass
class ABTestVariant:
    """A/B 测试变体"""
    name: str                    # 变体名称，如 "control"、"treatment"
    prompt_name: str             # 对应的 prompt 名称
    prompt_version: int          # 对应的 prompt 版本号
    weight: float = 1.0          # 流量权重（相对值）


@dataclass
class ABTest:
    """A/B 测试配置"""
    test_id: str                 # 测试唯一 ID
    description: str             # 测试描述
    variants: List[ABTestVariant]  # 变体列表
    enabled: bool = True         # 是否启用
    created_at: float = field(default_factory=time.time)


class ABTestRegistry:
    """A/B 测试注册表

    功能：
    - 注册和管理 A/B 测试
    - 根据流量权重路由请求到不同变体
    - 记录每个变体的性能指标
    - 生成对比报告
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(settings.DATA_DIR / "ab_tests.db")
        self._local = threading.local()
        self._initialized = False
        self._tests: Dict[str, ABTest] = {}

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
                CREATE TABLE IF NOT EXISTS ab_test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT NOT NULL,
                    variant_name TEXT NOT NULL,
                    question TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    latency_ms INTEGER DEFAULT 0,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    estimated_cost REAL,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ab_test_id
                    ON ab_test_results(test_id);
                CREATE INDEX IF NOT EXISTS idx_ab_test_variant
                    ON ab_test_results(test_id, variant_name);
            """)
            conn.commit()
        finally:
            conn.close()

    def register(self, test: ABTest) -> None:
        """注册一个 A/B 测试"""
        self._tests[test.test_id] = test
        logger.info(f"A/B 测试注册: {test.test_id} ({len(test.variants)} 个变体)")

    def get_test(self, test_id: str) -> Optional[ABTest]:
        """获取指定的 A/B 测试"""
        return self._tests.get(test_id)

    def route(self, test_id: str, question: str) -> Optional[ABTestVariant]:
        """根据流量权重路由到某个变体

        使用问题文本的哈希值确定路由，保证同一问题始终路由到同一变体。
        """
        test = self._tests.get(test_id)
        if not test or not test.enabled:
            return None

        # 用问题哈希确定路由（同一问题始终走同一变体）
        question_hash = int(hashlib.md5(question.encode()).hexdigest(), 16)
        total_weight = sum(v.weight for v in test.variants)
        position = (question_hash % 1000) / 1000.0 * total_weight

        cumulative = 0.0
        for variant in test.variants:
            cumulative += variant.weight
            if position < cumulative:
                return variant

        return test.variants[-1]

    def record(
        self,
        test_id: str,
        variant_name: str,
        question: str,
        success: bool,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: Optional[float] = None,
    ) -> None:
        """记录一次 A/B 测试结果"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO ab_test_results
            (test_id, variant_name, question, success, latency_ms,
             input_tokens, output_tokens, total_tokens, estimated_cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (test_id, variant_name, question, success, latency_ms,
             input_tokens, output_tokens, total_tokens, estimated_cost, time.time()),
        )
        conn.commit()

    def get_report(self, test_id: str) -> Dict[str, Any]:
        """生成 A/B 测试对比报告"""
        conn = self._get_conn()

        rows = conn.execute(
            """
            SELECT
                variant_name,
                COUNT(*) as total_requests,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                AVG(latency_ms) as avg_latency,
                AVG(total_tokens) as avg_tokens,
                AVG(estimated_cost) as avg_cost
            FROM ab_test_results
            WHERE test_id = ?
            GROUP BY variant_name
            """,
            (test_id,),
        ).fetchall()

        variants = {}
        for row in rows:
            variant_name = row[0]
            total = row[1]
            success = row[2]
            variants[variant_name] = {
                "total_requests": total,
                "success_count": success,
                "success_rate": success / total if total > 0 else 0,
                "avg_latency_ms": round(row[3], 1) if row[3] else 0,
                "avg_tokens": round(row[4], 1) if row[4] else 0,
                "avg_cost": round(row[5], 6) if row[5] else None,
            }

        # 计算提升度
        if len(variants) == 2:
            keys = list(variants.keys())
            a, b = keys[0], keys[1]
            rate_a = variants[a]["success_rate"]
            rate_b = variants[b]["success_rate"]
            if rate_a > 0:
                variants["_lift"] = {
                    "from": a,
                    "to": b,
                    "success_rate_lift": round((rate_b - rate_a) / rate_a * 100, 2),
                    "latency_diff_ms": round(
                        variants[b]["avg_latency_ms"] - variants[a]["avg_latency_ms"], 1
                    ),
                }

        return {
            "test_id": test_id,
            "variants": variants,
        }

    def list_tests(self) -> List[Dict[str, Any]]:
        """列出所有注册的 A/B 测试"""
        return [
            {
                "test_id": test.test_id,
                "description": test.description,
                "variants": [v.name for v in test.variants],
                "enabled": test.enabled,
            }
            for test in self._tests.values()
        ]


# 全局注册表
ab_test_registry = ABTestRegistry()
