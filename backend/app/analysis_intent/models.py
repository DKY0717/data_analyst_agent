"""分层意图、Schema Grounding、路由和主动澄清的稳定数据契约。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class IntentSlot(BaseModel):
    """表达指标或维度等业务概念，不在意图层提前绑定物理表。"""

    concept: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence: str = ""


class FilterSlot(IntentSlot):
    """表达结构化过滤条件，供后续 Grounding 映射到物理字段。"""

    operator: str = Field(min_length=1)
    value: Any


class RankingSlot(BaseModel):
    """表达 Top-N 与排序方向，避免 SQL Generator 再次猜测。"""

    direction: Literal["asc", "desc"]
    limit: int = Field(gt=0)


class AnalysisIntent(BaseModel):
    """保存规则与 LLM 合并后的完整分析意图。"""

    task_types: list[str] = Field(default_factory=list)
    metrics: list[IntentSlot] = Field(default_factory=list)
    dimensions: list[IntentSlot] = Field(default_factory=list)
    filters: list[FilterSlot] = Field(default_factory=list)
    time_granularity: str | None = None
    ranking: RankingSlot | None = None
    missing_slots: list[str] = Field(default_factory=list)
    # 冲突必须显式保留，风险决策层才能判断是否需要主动澄清。
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    overall_confidence: float = Field(default=0, ge=0, le=1)


class GroundingCandidate(BaseModel):
    """描述业务概念映射到物理 Schema 的一个可解释候选。"""

    candidate_id: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    tables: list[str]
    columns: list[str]
    score: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class GroundingResult(BaseModel):
    """保留一个业务概念的全部 Grounding 候选及稳定排序。"""

    concept: str = Field(min_length=1)
    candidates: list[GroundingCandidate] = Field(default_factory=list)


class SchemaRoute(BaseModel):
    """描述覆盖 Grounding 候选的最小连通 Schema 子图。"""

    selected_tables: list[str] = Field(default_factory=list)
    join_edges: list[tuple[str, str]] = Field(default_factory=list)
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)


class ClarificationOption(BaseModel):
    """使用稳定候选 ID 连接展示文案、任务恢复与分层评测。"""

    candidate_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ClarificationRequest(BaseModel):
    """表达一次主动澄清请求，并限制最多两轮避免无限对话。"""

    clarification_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: list[ClarificationOption] = Field(min_length=1)
    max_rounds: int = Field(default=2, ge=1, le=2)
