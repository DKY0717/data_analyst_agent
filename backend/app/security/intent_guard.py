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

    _CLAUSE_SEPARATOR = _pattern(
        r"[，,。！？?!；;]+|然后|随后|接着|同时|而是|并且|但是|并|但|却"
        r"|后(?=\s*(?:删除|清空|销毁|修改|更新|导出|读取|查看|访问|绕过|忽略|禁用|跳过))"
        r"|\b(?:then|and\s+then|and|but|while|whereas)\b"
    )
    _SAFE_ACTION_CONTEXT = _pattern(
        r"(?:不要|不应|不能|禁止|无需)\s*"
        r"(?:删除|清空|销毁|修改|更新|显示|查看|读取|获取|导出|下载|提取|访问|打开|绕过|忽略|禁用|跳过)"
        r"(?:所有|全部|批量|完整)?(?:客户)?\s*"
        r"(?:订单表?|支付(?:状态|记录)?|客户表?|数据库|数据表|手机号|电话号码|身份证|邮箱"
        r"|api[_\s-]?(?:key|token)|访问令牌|密钥|密码|系统文件|主机文件|系统表|sql\s*guard|安全(?:规则|限制|检查|控制))"
        r"|(?:能否|是否可以|可否)\s*(?:删除|清空|修改|更新)"
        r"(?:所有|全部)?(?:订单表?|支付(?:状态|记录)?|客户表?|数据库|数据表)"
        r"|\b(?:do\s+not|don't|should(?:n't|\s+not)|must\s+not|never)\s+"
        r"(?:delete|remove|show|read|export|access|bypass|ignore|disable)\b\s*"
        r"(?:all|every|bulk|entire|the\s+entire)?\s*"
        r"(?:orders?|payments?|customers?|database|tables?|api[_\s-]?(?:key|token)"
        r"|access[_\s-]?token|secret|password|credentials?|system\s+files?|host\s+files?"
        r"|system\s+tables?|sql\s*guard|security\s+(?:rules?|checks?|controls?))\b"
        r"|\b(?:how\s+can\s+we\s+)?(?:prevent|avoid|prohibit|block)\s+"
        r"(?:access|export|delete|remove|show|read|bypass|ignore|disable)\b\s*(?:to\s+)?"
        r"(?:orders?|payments?|customers?|database|tables?|api[_\s-]?(?:key|token)"
        r"|access[_\s-]?token|secret|password|credentials?|system\s+files?|host\s+files?"
        r"|system\s+tables?|sql\s*guard|security\s+(?:rules?|checks?|controls?))\b"
    )
    _SAFE_MUTATION_CONTEXT = _pattern(
        r"(?:被|已)\s*(?:删除|修改|更新)(?:的)?\s*(?:订单|支付|客户|数据)"
    )

    _SECURITY_BYPASS_RULE = IntentRule(
        rule_id="block_security_bypass_intent",
        reason="请求包含明确的安全控制绕过意图",
        category="security_bypass",
        action=_pattern(r"绕过|忽略|禁用|跳过|\b(?:bypass|ignore|disable|skip)\b"),
        target=_pattern(
            r"sql\s*guard|安全(?:规则|限制|检查|控制)|系统表"
            r"|\bsecurity\s+(?:rules?|checks?|controls?)\b|\bsystem\s+tables?\b"
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
                r"|\b(?:drop|delete|truncate|erase|remove)\b\s+(?:all|every|the\s+entire)?"
                r"|\b(?:update|change|set)\b\s+.{0,40}\s+(?:to|=)"
            ),
            target=_pattern(
                r"订单表?|支付(?:状态|记录)?|客户表?|数据库|数据表"
                r"|\b(?:orders?|payments?|customers?|database|tables?)\b"
            ),
        ),
        IntentRule(
            rule_id="block_credential_access_intent",
            reason="请求包含明确的凭据访问意图",
            category="credential_access",
            action=_pattern(r"查看|显示|读取|获取|导出|\b(?:show|read|get|reveal|export)\b"),
            target=_pattern(
                r"\bqwen_api_key\b|\bapi[_\s-]?(?:key|token)\b|访问令牌|密钥|密码"
                r"|\baccess[_\s-]?token\b|\b(?:secret|password|credentials?)\b"
            ),
        ),
        IntentRule(
            rule_id="block_system_access_intent",
            reason="请求包含明确的系统资源访问意图",
            category="system_access",
            action=_pattern(r"读取|查看|打开|访问|\b(?:read|show|open|access)\b"),
            target=_pattern(
                r"/etc/passwd|/etc/shadow|系统文件|主机文件"
                r"|windows\\system32|\b(?:system|host)\s+files?\b"
            ),
        ),
        IntentRule(
            rule_id="block_sensitive_export_intent",
            reason="请求包含明确的批量敏感数据导出意图",
            category="sensitive_export",
            action=_pattern(r"导出|下载|提取|\b(?:export|download|extract)\b"),
            target=_pattern(
                r"手机号|电话号码|身份证|邮箱|\bphone(?:\s+numbers?)?\b|\b(?:emails?|ssn)\b"
            ),
            # 批量标记是高置信条件，可降低正常聚合分析被误判的概率。
            extra=_pattern(r"全部|所有|批量|完整|\b(?:all|every|bulk|entire)\b"),
        ),
    )

    def _clean_fragments(self, question: str) -> list[str]:
        # 只消除明确安全动作及其目标，不删除整个片段，避免吞掉前后危险命令。
        fragments = []
        for fragment in self._CLAUSE_SEPARATOR.split(question):
            cleaned = self._SAFE_ACTION_CONTEXT.sub("", fragment).strip()
            if cleaned:
                fragments.append(cleaned)
        return fragments

    def validate(self, question: str) -> dict:
        """返回固定四字段的安全判定结果。"""
        normalized_question = question.strip() if isinstance(question, str) else ""

        # 每个逻辑片段独立匹配，防止一个片段的动作与另一个片段的目标错误组合。
        fragments = self._clean_fragments(normalized_question)
        for fragment in fragments:
            if self._SECURITY_BYPASS_RULE.matches(fragment):
                return self._SECURITY_BYPASS_RULE.blocked_result()

        # 规则只依赖文本组合匹配，不读取数据库、Schema、LLM 或 Agent 状态。
        for rule in self._RULES:
            for fragment in fragments:
                rule_candidate = fragment
                if rule.category == "data_mutation":
                    # 被动分析语态不代表执行修改，局部移除可保留同片段的明确危险命令。
                    rule_candidate = self._SAFE_MUTATION_CONTEXT.sub("", rule_candidate)
                if rule.matches(rule_candidate):
                    return rule.blocked_result()

        return SAFE_RESULT.copy()


intent_guard = IntentGuard()
