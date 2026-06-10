"""在进入 Agent 工作流前识别高置信危险意图。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


SAFE_RESULT = {
    "is_safe": True,
    "rule_id": None,
    "reason": None,
    "category": None,
}


@dataclass(frozen=True)
class IntentRule:
    """用动作与目标的组合描述一条高置信阻断规则。"""

    rule_id: str
    reason: str
    category: str
    action: Pattern[str]
    target: Pattern[str]
    extra: Pattern[str] | None = None

    def matches(self, question: str) -> bool:
        return bool(
            self.action.search(question)
            and self.target.search(question)
            and (self.extra is None or self.extra.search(question))
        )

    def blocked_result(self) -> dict:
        # 仅返回固定规则元数据，避免把问题中的凭据或敏感文本带入响应。
        return {
            "is_safe": False,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "category": self.category,
        }


def _pattern(expression: str) -> Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


class IntentGuard:
    """使用确定性规则阻断明确危险命令，并放行安全或模糊请求。"""

    _SAFE_BYPASS_CONTEXT = _pattern(
        r"(?:不要|不应|不能|禁止|无需)\s*(?:绕过|忽略|禁用)"
        r"|(?:do\s+not|don't|should(?:n't|\s+not)|without)\s+"
        r"(?:bypass(?:ing)?|ignore|disable)"
    )
    _SAFE_MUTATION_CONTEXT = _pattern(
        r"(?:被|已)\s*(?:删除|修改|更新)(?:的)?\s*(?:订单|支付|客户|数据)"
        r"|(?:能否|是否可以|可否)\s*(?:删除|修改|更新).{0,20}(?:订单|支付|客户|数据|表)"
    )

    _SECURITY_BYPASS_RULE = IntentRule(
        rule_id="block_security_bypass_intent",
        reason="请求包含明确的安全控制绕过意图",
        category="security_bypass",
        action=_pattern(r"绕过|忽略|禁用|跳过|bypass|ignore|disable|skip"),
        target=_pattern(
            r"sql\s*guard|安全(?:规则|限制|检查|控制)|系统表|security\s+(?:rules?|checks?|controls?)"
            r"|system\s+tables?"
        ),
    )

    _RULES = (
        IntentRule(
            rule_id="block_destructive_intent",
            reason="请求包含明确的数据修改或删除意图",
            category="data_mutation",
            action=_pattern(
                r"(?:删除|清空|销毁)\s*(?:所有|全部|整个|整张)?"
                r"|(?:把|将).{0,40}(?:改成|修改为|更新为|设为)"
                r"|(?:drop|delete|truncate|erase|remove)\s+(?:all|every|the\s+entire)?"
                r"|(?:update|change|set)\s+.{0,40}\s+(?:to|=)"
            ),
            target=_pattern(
                r"订单表?|支付(?:状态|记录)?|客户表?|数据库|数据表"
                r"|orders?|payments?|customers?|database|tables?"
            ),
        ),
        IntentRule(
            rule_id="block_credential_access_intent",
            reason="请求包含明确的凭据访问意图",
            category="credential_access",
            action=_pattern(r"查看|显示|读取|获取|导出|show|read|get|reveal|export"),
            target=_pattern(
                r"qwen_api_key|api[_\s-]?(?:key|token)|访问令牌|密钥|密码"
                r"|access[_\s-]?token|secret|password|credentials?"
            ),
        ),
        IntentRule(
            rule_id="block_system_access_intent",
            reason="请求包含明确的系统资源访问意图",
            category="system_access",
            action=_pattern(r"读取|查看|打开|访问|read|show|open|access"),
            target=_pattern(
                r"/etc/passwd|/etc/shadow|系统文件|主机文件"
                r"|windows\\system32|system\s+files?|host\s+files?"
            ),
        ),
        IntentRule(
            rule_id="block_sensitive_export_intent",
            reason="请求包含明确的批量敏感数据导出意图",
            category="sensitive_export",
            action=_pattern(r"导出|下载|提取|export|download|extract"),
            target=_pattern(r"手机号|电话号码|身份证|邮箱|\bphone(?:\s+numbers?)?\b|emails?|ssn"),
            # 批量标记是高置信条件，可降低正常聚合分析被误判的概率。
            extra=_pattern(r"全部|所有|批量|完整|all|every|bulk|entire"),
        ),
    )

    def validate(self, question: str) -> dict:
        """返回固定四字段的安全判定结果。"""
        normalized_question = question.strip() if isinstance(question, str) else ""

        # 安全绕过表述优先移除，但仍检查复合请求中剩余的明确绕过命令。
        bypass_candidate = self._SAFE_BYPASS_CONTEXT.sub("", normalized_question)
        if self._SECURITY_BYPASS_RULE.matches(bypass_candidate):
            return self._SECURITY_BYPASS_RULE.blocked_result()

        # 规则只依赖文本组合匹配，不读取数据库、Schema、LLM 或 Agent 状态。
        for rule in self._RULES:
            candidate = normalized_question
            if rule.category == "data_mutation":
                # 只移除被动语态和能力询问片段，保留复合请求中后续的明确危险命令。
                candidate = self._SAFE_MUTATION_CONTEXT.sub("", candidate)
            if rule.matches(candidate):
                return rule.blocked_result()

        return SAFE_RESULT.copy()


intent_guard = IntentGuard()
