"""核心路径黄金问题包加载与静态校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CORE_PATH_CATEGORIES = {
    "business_success",
    "business_metric",
    "follow_up",
    "permission",
    "safety_failure",
}


class CorePathCaseError(ValueError):
    """核心路径 case 配置错误。"""


@dataclass(frozen=True)
class CorePathCase:
    """把 YAML case 转成稳定对象，方便测试和脚本按字段访问。"""

    case_id: str
    question: str
    category: str
    demo_role: str | None
    linked_cases: list[dict[str, str]]
    expected_surfaces: list[str]
    success_criteria: str


class CorePathCaseLoader:
    """加载核心路径配置；只做静态校验，不调用 LLM 或数据库。"""

    def __init__(self, case_file: str | Path | None = None):
        self.case_file = (
            Path(case_file)
            if case_file
            else Path(__file__).parent / "cases" / "core_path_cases.yaml"
        )

    def load_cases(self) -> list[CorePathCase]:
        """读取并校验全部 case，作为前端和演示脚本对齐的事实来源。"""
        payload = self._load_payload()
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, list):
            raise CorePathCaseError(f"{self.case_file} must contain a cases list")

        cases = [self._parse_case(raw_case) for raw_case in raw_cases]
        self._validate_unique_ids(cases)
        return cases

    def group_by_category(self) -> dict[str, list[CorePathCase]]:
        """按类别分组，避免调用方在多处重复维护筛选逻辑。"""
        grouped = {category: [] for category in sorted(CORE_PATH_CATEGORIES)}
        for case in self.load_cases():
            grouped[case.category].append(case)
        return grouped

    def _load_payload(self) -> dict[str, Any]:
        if not self.case_file.exists():
            raise CorePathCaseError(f"core path case file not found: {self.case_file}")
        with self.case_file.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file)
        if not isinstance(payload, dict):
            raise CorePathCaseError(f"{self.case_file} must be a YAML mapping")
        return payload

    def _parse_case(self, raw_case: Any) -> CorePathCase:
        if not isinstance(raw_case, dict):
            raise CorePathCaseError("each core path case must be a mapping")
        case_id = self._required_string(raw_case, "id")
        category = self._required_string(raw_case, "category")
        if category not in CORE_PATH_CATEGORIES:
            raise CorePathCaseError(f"{case_id}: unknown category {category}")

        linked_cases = raw_case.get("linked_cases", [])
        if not isinstance(linked_cases, list):
            raise CorePathCaseError(f"{case_id}: linked_cases must be a list")
        for link in linked_cases:
            # link 使用 source/id 形式，是为了同时关联 YAML case 和代码内置权限 case。
            if not isinstance(link, dict) or not link.get("source") or not link.get("id"):
                raise CorePathCaseError(f"{case_id}: linked case must include source and id")

        expected_surfaces = raw_case.get("expected_surfaces", [])
        if not isinstance(expected_surfaces, list) or not expected_surfaces:
            raise CorePathCaseError(f"{case_id}: expected_surfaces must be a non-empty list")

        return CorePathCase(
            case_id=case_id,
            question=self._required_string(raw_case, "question"),
            category=category,
            demo_role=raw_case.get("demo_role"),
            linked_cases=linked_cases,
            expected_surfaces=[str(item) for item in expected_surfaces],
            success_criteria=self._required_string(raw_case, "success_criteria"),
        )

    @staticmethod
    def _required_string(raw_case: dict[str, Any], field: str) -> str:
        value = raw_case.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CorePathCaseError(f"core path case missing required string field: {field}")
        return value.strip()

    @staticmethod
    def _validate_unique_ids(cases: list[CorePathCase]) -> None:
        seen: set[str] = set()
        for case in cases:
            if case.case_id in seen:
                raise CorePathCaseError(f"duplicate core path case id: {case.case_id}")
            seen.add(case.case_id)
