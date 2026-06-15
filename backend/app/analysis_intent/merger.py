"""合并规则与 LLM 分析意图，同时显式保留候选冲突。"""

from typing import Any

from .models import AnalysisIntent, FilterSlot, IntentSlot


class AnalysisIntentMerger:
    """让高确定性规则槽位优先，并将不一致转换为可校准风险证据。"""

    def merge(
        self,
        rule_intent: AnalysisIntent,
        llm_intent: AnalysisIntent,
    ) -> AnalysisIntent:
        conflicts = [
            *rule_intent.conflicts,
            *llm_intent.conflicts,
        ]
        metrics = self._merge_slots(rule_intent.metrics, llm_intent.metrics)
        dimensions = self._merge_slots(
            rule_intent.dimensions, llm_intent.dimensions
        )
        self._record_disjoint_slot_conflict(
            conflicts, "metrics", rule_intent.metrics, llm_intent.metrics
        )
        self._record_disjoint_slot_conflict(
            conflicts, "dimensions", rule_intent.dimensions, llm_intent.dimensions
        )

        ranking = rule_intent.ranking or llm_intent.ranking
        if (
            rule_intent.ranking
            and llm_intent.ranking
            and rule_intent.ranking != llm_intent.ranking
        ):
            conflicts.append(
                {
                    "slot": "ranking",
                    "rule": rule_intent.ranking.model_dump(),
                    "llm": llm_intent.ranking.model_dump(),
                }
            )

        time_granularity = (
            rule_intent.time_granularity or llm_intent.time_granularity
        )
        if (
            rule_intent.time_granularity
            and llm_intent.time_granularity
            and rule_intent.time_granularity != llm_intent.time_granularity
        ):
            conflicts.append(
                {
                    "slot": "time_granularity",
                    "rule": rule_intent.time_granularity,
                    "llm": llm_intent.time_granularity,
                }
            )

        overall_confidence = max(
            rule_intent.overall_confidence,
            llm_intent.overall_confidence,
        )
        if conflicts:
            # 冲突降低整体置信度，但不丢弃任何候选，交由风险层决定是否澄清。
            overall_confidence *= 0.8

        missing_slots = list(
            dict.fromkeys([*rule_intent.missing_slots, *llm_intent.missing_slots])
        )
        if metrics and "metric" in missing_slots:
            missing_slots.remove("metric")

        return AnalysisIntent(
            task_types=list(
                dict.fromkeys([*rule_intent.task_types, *llm_intent.task_types])
            ),
            metrics=metrics,
            dimensions=dimensions,
            filters=self._merge_filters(rule_intent.filters, llm_intent.filters),
            time_granularity=time_granularity,
            ranking=ranking,
            missing_slots=missing_slots,
            conflicts=conflicts,
            overall_confidence=overall_confidence,
        )

    @staticmethod
    def _merge_slots(
        rule_slots: list[IntentSlot],
        llm_slots: list[IntentSlot],
    ) -> list[IntentSlot]:
        """同概念优先保留高确定性规则槽位，其余候选按来源顺序追加。"""
        merged: dict[str, IntentSlot] = {}
        for slot in [*rule_slots, *llm_slots]:
            if slot.concept not in merged:
                merged[slot.concept] = slot.model_copy(deep=True)
        return list(merged.values())

    @staticmethod
    def _merge_filters(
        rule_filters: list[FilterSlot],
        llm_filters: list[FilterSlot],
    ) -> list[FilterSlot]:
        merged = {}
        for item in [*rule_filters, *llm_filters]:
            key = (item.concept, item.operator, repr(item.value))
            if key not in merged:
                merged[key] = item.model_copy(deep=True)
        return list(merged.values())

    @staticmethod
    def _record_disjoint_slot_conflict(
        conflicts: list[dict[str, Any]],
        slot_name: str,
        rule_slots: list[IntentSlot],
        llm_slots: list[IntentSlot],
    ) -> None:
        """两侧均有输出但完全不重合时，记录稳定概念列表供风险层判断。"""
        rule_concepts = {slot.concept for slot in rule_slots}
        llm_concepts = {slot.concept for slot in llm_slots}
        if rule_concepts and llm_concepts and rule_concepts.isdisjoint(llm_concepts):
            conflicts.append(
                {
                    "slot": slot_name,
                    "rule": sorted(rule_concepts),
                    "llm": sorted(llm_concepts),
                }
            )
