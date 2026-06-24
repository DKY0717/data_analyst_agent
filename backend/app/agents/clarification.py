# 主动澄清模块
# 当意图解析置信度低或缺失关键槽位时，生成结构化澄清请求。

from typing import Any

from ..analysis_intent.models import AnalysisIntent, ClarificationOption, ClarificationRequest


class ClarificationEngine:
    """基于意图解析结果判断是否需要主动澄清。"""

    CONFIDENCE_THRESHOLD = 0.5
    MAX_CLARIFICATION_ROUNDS = 2

    def check(self, intent: AnalysisIntent) -> ClarificationRequest | None:
        """检查是否需要澄清；不需要时返回 None。"""
        if intent.overall_confidence >= self.CONFIDENCE_THRESHOLD and not intent.missing_slots:
            return None

        reason = self._build_reason(intent)
        question = self._build_question(intent)
        options = self._build_options(intent)

        if not options:
            return None

        return ClarificationRequest(
            clarification_id=f"clarify_{hash(question) % 10000:04d}",
            reason=reason,
            question=question,
            options=options,
            max_rounds=self.MAX_CLARIFICATION_ROUNDS,
        )

    def _build_reason(self, intent: AnalysisIntent) -> str:
        """生成澄清原因。"""
        reasons = []
        if "metric" in intent.missing_slots:
            reasons.append("未识别到明确的分析指标")
        if intent.conflicts:
            reasons.append(f"存在 {len(intent.conflicts)} 个意图冲突")
        if intent.overall_confidence < self.CONFIDENCE_THRESHOLD:
            reasons.append(f"整体置信度较低 ({intent.overall_confidence:.0%})")
        return "；".join(reasons) if reasons else "需要补充信息"

    def _build_question(self, intent: AnalysisIntent) -> str:
        """生成面向用户的澄清问题。"""
        if "metric" in intent.missing_slots:
            return "您想分析什么指标？例如：销售额、订单数、退款率等。"
        if intent.conflicts:
            return "检测到多个可能的分析方向，请确认您想分析的具体内容。"
        return "请补充更多分析细节。"

    def _build_options(self, intent: AnalysisIntent) -> list[ClarificationOption]:
        """基于已有线索生成候选选项。"""
        options = []

        # 如果有部分指标但缺失维度，推荐常见维度
        if intent.metrics and not intent.dimensions:
            for dim in ["region", "month", "category"]:
                options.append(ClarificationOption(
                    candidate_id=f"dim_{dim}",
                    label=f"按{self._dim_label(dim)}拆分",
                    description=f"将当前指标按{self._dim_label(dim)}维度分组",
                ))

        # 如果完全缺失指标，推荐常用指标
        if "metric" in intent.missing_slots:
            for metric, label in [
                ("sales_amount", "销售额"),
                ("order_count", "订单数"),
                ("customer_count", "客户数"),
            ]:
                options.append(ClarificationOption(
                    candidate_id=f"metric_{metric}",
                    label=label,
                    description=f"分析{label}相关的数据",
                ))

        return options[:3]

    @staticmethod
    def _dim_label(dim: str) -> str:
        labels = {"region": "地区", "month": "月份", "category": "商品类别"}
        return labels.get(dim, dim)


clarification_engine = ClarificationEngine()
