"""使用可解释规则提取高确定性分析意图槽位。"""

import re
from typing import Any

from .models import AnalysisIntent, FilterSlot, IntentSlot, RankingSlot
from ..schema_context.metadata_catalog import MetadataCatalog


YEAR_PATTERN = re.compile(r"(?P<year>20\d{2})\s*年")
TOP_PATTERNS = (
    re.compile(r"(?:前|top)\s*(?P<limit>\d+)", re.IGNORECASE),
    re.compile(
        r"(?:最高|最多|最大|最低|最少|最小)(?:的)?\s*(?P<limit>\d+)",
        re.IGNORECASE,
    ),
)
ASC_PATTERN = re.compile(r"最低|最少|最小|升序|asc", re.IGNORECASE)


class AnalysisIntentRuleParser:
    """解析时间、排序、Top-N 与显式业务别名，不猜测隐式概念。"""

    def __init__(self, catalog: MetadataCatalog | None = None):
        self.catalog = catalog or MetadataCatalog.from_sources()

    def parse(self, question: str) -> AnalysisIntent:
        """将自然语言问题转换为规则层 AnalysisIntent 候选。"""
        normalized_question = question.strip() if isinstance(question, str) else ""
        metrics = self._extract_semantic_slots(normalized_question, self.catalog.metrics)
        dimensions = self._extract_semantic_slots(
            normalized_question, self.catalog.dimensions
        )
        filters = self._extract_year_filters(normalized_question)
        ranking = self._extract_ranking(normalized_question)

        task_types = []
        if metrics:
            task_types.append("aggregation")
        if ranking:
            task_types.append("ranking")

        # 规则层没有识别到指标时显式留空，后续 LLM 或主动澄清负责补全。
        missing_slots = [] if metrics else ["metric"]
        extracted_count = len(metrics) + len(dimensions) + len(filters)
        if ranking:
            extracted_count += 1

        return AnalysisIntent(
            task_types=task_types,
            metrics=metrics,
            dimensions=dimensions,
            filters=filters,
            ranking=ranking,
            missing_slots=missing_slots,
            overall_confidence=0.95 if extracted_count else 0.0,
        )

    @staticmethod
    def _extract_semantic_slots(
        question: str, items: dict[str, dict[str, Any]]
    ) -> list[IntentSlot]:
        """按文本首次出现位置召回语义概念，并合并同一概念的多个别名。"""
        matches = []
        normalized_question = question.casefold()
        for key, value in items.items():
            aliases = [key, value.get("name", ""), *value.get("aliases", [])]
            positions = [
                (normalized_question.find(str(alias).casefold()), str(alias))
                for alias in aliases
                if alias and str(alias).casefold() in normalized_question
            ]
            if not positions:
                continue
            position, evidence = min(
                positions,
                key=lambda item: (item[0], -len(item[1]), item[1]),
            )
            matches.append(
                (
                    position,
                    key,
                    IntentSlot(
                        concept=key,
                        confidence=0.95,
                        evidence=evidence,
                    ),
                )
            )

        return [
            slot
            for _, _, slot in sorted(matches, key=lambda item: (item[0], item[1]))
        ]

    @staticmethod
    def _extract_year_filters(question: str) -> list[FilterSlot]:
        """年份属于高确定性槽位，重复年份只保留一次。"""
        filters = []
        seen_years = set()
        for match in YEAR_PATTERN.finditer(question):
            year = int(match.group("year"))
            if year in seen_years:
                continue
            seen_years.add(year)
            filters.append(
                FilterSlot(
                    concept="order_date",
                    operator="year_equals",
                    value=year,
                    confidence=1.0,
                    evidence=match.group(0),
                )
            )
        return filters

    @staticmethod
    def _extract_ranking(question: str) -> RankingSlot | None:
        """提取 Top-N 与方向；只写排序未给数量时不创建不完整 RankingSlot。"""
        limit_matches = [
            match
            for pattern in TOP_PATTERNS
            if (match := pattern.search(question)) is not None
        ]
        if not limit_matches:
            return None
        limit_match = min(limit_matches, key=lambda match: match.start())

        if ASC_PATTERN.search(question):
            direction = "asc"
        else:
            # “前 N”与 Top-N 在未声明方向时按业务惯例解释为降序。
            direction = "desc"
        return RankingSlot(
            direction=direction,
            limit=int(limit_match.group("limit")),
        )
