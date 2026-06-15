"""比较 Agent 与黄金参考查询的结构化结果。"""

from collections import deque
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SUPPORTED_MODES = {"unordered", "ordered", "top_n", "scalar"}
FAILURE_ORDER = (
    "column_mismatch",
    "row_count_mismatch",
    "value_mismatch",
    "order_mismatch",
    "fixed_assertion_failed",
)


class ResultComparator:
    """以确定性规则比较分析结果，不依赖数据库或 LLM。"""

    def __init__(self, max_diff_samples: int = 5):
        # 差异样本只用于定位问题；非法配置回退到安全默认值，避免泄露完整结果集。
        self.max_diff_samples = (
            min(max_diff_samples, 5)
            if isinstance(max_diff_samples, int)
            and not isinstance(max_diff_samples, bool)
            and max_diff_samples >= 0
            else 5
        )

    def compare(
        self,
        actual: dict,
        expected: dict,
        comparison: dict,
        fixed_assertions: dict | None = None,
    ) -> dict:
        """比较两份结果；任何畸形输入或意外异常都转换为稳定失败。"""
        try:
            actual_columns, actual_rows = self._validate_result(actual)
            expected_columns, expected_rows = self._validate_result(expected)
            mode, required_columns, tolerance = self._validate_comparison(
                comparison, expected_columns
            )
            self._validate_fixed_assertions(fixed_assertions)

            actual_indexes = self._column_indexes(actual_columns)
            expected_indexes = self._column_indexes(expected_columns)
            required_keys = [column.casefold() for column in required_columns]
            columns_matched = all(
                key in actual_indexes and key in expected_indexes for key in required_keys
            )

            if columns_matched:
                actual_projected = self._project_rows(
                    actual_rows, actual_indexes, required_keys
                )
                expected_projected = self._project_rows(
                    expected_rows, expected_indexes, required_keys
                )
            else:
                actual_projected = []
                expected_projected = []

            row_count_matched = self._row_count_matches(
                mode, actual_rows, expected_rows
            )
            values_matched = (
                columns_matched
                and row_count_matched
                and self._multiset_matches(actual_projected, expected_projected, tolerance)
            )
            order_matched = self._order_matches(
                mode,
                columns_matched,
                row_count_matched,
                actual_projected,
                expected_projected,
                tolerance,
            )
            fixed_assertions_matched = self._fixed_assertions_match(
                expected_columns,
                expected_rows,
                fixed_assertions,
                tolerance,
            )

            states = {
                "column_mismatch": not columns_matched,
                "row_count_mismatch": not row_count_matched,
                # 列不匹配时无法可靠比较值，避免额外报告误导性的 value_mismatch。
                "value_mismatch": columns_matched and not values_matched,
                "order_mismatch": (
                    mode in {"ordered", "top_n"}
                    and columns_matched
                    and not order_matched
                ),
                "fixed_assertion_failed": not fixed_assertions_matched,
            }
            failure_types = [
                failure_type
                for failure_type in FAILURE_ORDER
                if states[failure_type]
            ]
            diff_samples = self._build_diff_samples(
                actual_columns=actual_columns,
                expected_columns=expected_columns,
                required_columns=required_columns,
                actual_rows=actual_projected,
                expected_rows=expected_projected,
                columns_matched=columns_matched,
                values_matched=values_matched,
                tolerance=tolerance,
            )

            return {
                "columns_matched": columns_matched,
                "row_count_matched": row_count_matched,
                "values_matched": values_matched,
                "order_matched": order_matched,
                "fixed_assertions_matched": fixed_assertions_matched,
                "result_correct": not failure_types,
                "failure_types": failure_types,
                "diff_samples": diff_samples,
            }
        except Exception:
            # 比较器位于批量评测链路中，单条坏数据必须稳定失败，不能中断后续 case。
            return self._unexpected_error_result()

    @staticmethod
    def _unexpected_error_result() -> Dict[str, Any]:
        return {
            "columns_matched": False,
            "row_count_matched": False,
            "values_matched": False,
            "order_matched": False,
            "fixed_assertions_matched": False,
            "result_correct": False,
            "failure_types": ["unexpected_error"],
            "diff_samples": [],
        }

    @classmethod
    def _validate_result(
        cls, result: Any
    ) -> Tuple[List[str], List[Sequence[Any]]]:
        if not isinstance(result, dict):
            raise ValueError("result must be a dict")

        columns = result.get("columns")
        rows = result.get("rows")
        if not cls._is_sequence(columns) or not all(
            isinstance(column, str) and column for column in columns
        ):
            raise ValueError("columns must be a sequence of non-empty strings")
        if not cls._is_sequence(rows):
            raise ValueError("rows must be a sequence")

        column_keys = [column.casefold() for column in columns]
        if len(column_keys) != len(set(column_keys)):
            raise ValueError("columns must be unique ignoring case")
        for row in rows:
            if not cls._is_sequence(row) or len(row) != len(columns):
                raise ValueError("each row must match the columns")
        return list(columns), list(rows)

    @classmethod
    def _validate_comparison(
        cls, comparison: Any, expected_columns: Sequence[str]
    ) -> Tuple[str, List[str], Decimal]:
        if not isinstance(comparison, dict):
            raise ValueError("comparison must be a dict")

        mode = comparison.get("mode")
        if mode not in SUPPORTED_MODES:
            raise ValueError("unsupported comparison mode")

        required_columns = comparison.get("required_columns", expected_columns)
        if not cls._is_sequence(required_columns) or not all(
            isinstance(column, str) and column for column in required_columns
        ):
            raise ValueError("required_columns must contain strings")
        required_keys = [column.casefold() for column in required_columns]
        if len(required_keys) != len(set(required_keys)):
            raise ValueError("required_columns must be unique ignoring case")

        tolerance = cls._to_tolerance(comparison.get("absolute_tolerance", 0.001))
        return mode, list(required_columns), tolerance

    @classmethod
    def _validate_fixed_assertions(cls, fixed_assertions: Any) -> None:
        if fixed_assertions is None:
            return
        if not isinstance(fixed_assertions, dict) or not set(fixed_assertions).issubset(
            {"row_count", "sum_column", "scalar"}
        ):
            raise ValueError("unsupported fixed assertion")

        if "row_count" in fixed_assertions:
            row_count = fixed_assertions["row_count"]
            if (
                not isinstance(row_count, int)
                or isinstance(row_count, bool)
                or row_count < 0
            ):
                raise ValueError("row_count assertion must be a non-negative integer")

        for assertion_name in ("sum_column", "scalar"):
            if assertion_name not in fixed_assertions:
                continue
            assertion = fixed_assertions[assertion_name]
            allowed_keys = {"column", "value", "absolute_tolerance"}
            if (
                not isinstance(assertion, dict)
                or not {"column", "value"}.issubset(assertion)
                or not set(assertion).issubset(allowed_keys)
                or not isinstance(assertion["column"], str)
                or not assertion["column"]
                or not cls._is_number(assertion["value"])
            ):
                raise ValueError("malformed fixed assertion")
            if "absolute_tolerance" in assertion:
                cls._to_tolerance(assertion["absolute_tolerance"])

    @staticmethod
    def _is_sequence(value: Any) -> bool:
        return isinstance(value, (list, tuple))

    @staticmethod
    def _column_indexes(columns: Sequence[str]) -> Dict[str, int]:
        return {column.casefold(): index for index, column in enumerate(columns)}

    @staticmethod
    def _project_rows(
        rows: Sequence[Sequence[Any]],
        indexes: Dict[str, int],
        required_keys: Sequence[str],
    ) -> List[Tuple[Any, ...]]:
        return [tuple(row[indexes[key]] for key in required_keys) for row in rows]

    @staticmethod
    def _row_count_matches(
        mode: str, actual_rows: Sequence[Any], expected_rows: Sequence[Any]
    ) -> bool:
        if mode == "scalar":
            return len(actual_rows) == len(expected_rows) == 1
        return len(actual_rows) == len(expected_rows)

    @classmethod
    def _order_matches(
        cls,
        mode: str,
        columns_matched: bool,
        row_count_matched: bool,
        actual_rows: Sequence[Sequence[Any]],
        expected_rows: Sequence[Sequence[Any]],
        tolerance: Decimal,
    ) -> bool:
        if mode not in {"ordered", "top_n"}:
            return True
        return (
            columns_matched
            and row_count_matched
            and all(
                cls._row_matches(actual, expected, tolerance)
                for actual, expected in zip(actual_rows, expected_rows)
            )
        )

    @classmethod
    def _multiset_matches(
        cls,
        actual_rows: Sequence[Sequence[Any]],
        expected_rows: Sequence[Sequence[Any]],
        tolerance: Decimal,
    ) -> bool:
        if len(actual_rows) != len(expected_rows):
            return False

        # 容差会破坏普通哈希 Counter 的等价关系，因此使用二分图匹配保留重复行语义。
        candidates = [
            [
                expected_index
                for expected_index, expected in enumerate(expected_rows)
                if cls._row_matches(actual, expected, tolerance)
            ]
            for actual in actual_rows
        ]
        matched_actual_by_expected: Dict[int, int] = {}
        matched_expected_by_actual: Dict[int, int] = {}

        for start_actual in range(len(actual_rows)):
            queue = deque([start_actual])
            visited_actual = {start_actual}
            visited_expected = set()
            parent_actual_by_expected: Dict[int, int] = {}
            unmatched_expected = None

            # 使用迭代增广路径，避免 1000 行重复结果触发 Python 递归深度限制。
            while queue and unmatched_expected is None:
                actual_index = queue.popleft()
                for expected_index in candidates[actual_index]:
                    if expected_index in visited_expected:
                        continue
                    visited_expected.add(expected_index)
                    parent_actual_by_expected[expected_index] = actual_index
                    previous_actual = matched_actual_by_expected.get(expected_index)
                    if previous_actual is None:
                        unmatched_expected = expected_index
                        break
                    if previous_actual not in visited_actual:
                        visited_actual.add(previous_actual)
                        queue.append(previous_actual)

            if unmatched_expected is None:
                return False

            expected_index = unmatched_expected
            while True:
                actual_index = parent_actual_by_expected[expected_index]
                previous_expected = matched_expected_by_actual.get(actual_index)
                matched_actual_by_expected[expected_index] = actual_index
                matched_expected_by_actual[actual_index] = expected_index
                if previous_expected is None:
                    break
                expected_index = previous_expected

        return True

    @classmethod
    def _row_matches(
        cls, actual: Sequence[Any], expected: Sequence[Any], tolerance: Decimal
    ) -> bool:
        return len(actual) == len(expected) and all(
            cls._value_matches(actual_value, expected_value, tolerance)
            for actual_value, expected_value in zip(actual, expected)
        )

    @classmethod
    def _value_matches(cls, actual: Any, expected: Any, tolerance: Decimal) -> bool:
        if cls._is_number(actual) and cls._is_number(expected):
            return abs(cls._to_decimal(actual) - cls._to_decimal(expected)) <= tolerance
        return cls._normalize_non_number(actual) == cls._normalize_non_number(expected)

    @staticmethod
    def _normalize_non_number(value: Any) -> Any:
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        return value

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (Decimal, int, float)) and not isinstance(value, bool)

    @classmethod
    def _to_decimal(cls, value: Any) -> Decimal:
        if not cls._is_number(value):
            raise ValueError("value must be numeric")
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("numeric value must be finite")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid numeric value") from exc
        if not decimal_value.is_finite():
            raise ValueError("numeric value must be finite")
        return decimal_value

    @classmethod
    def _to_tolerance(cls, value: Any) -> Decimal:
        tolerance = cls._to_decimal(value)
        if tolerance < 0:
            raise ValueError("absolute tolerance must be non-negative")
        return tolerance

    @classmethod
    def _fixed_assertions_match(
        cls,
        expected_columns: Sequence[str],
        expected_rows: Sequence[Sequence[Any]],
        fixed_assertions: Optional[dict],
        default_tolerance: Decimal,
    ) -> bool:
        if not fixed_assertions:
            return True

        indexes = cls._column_indexes(expected_columns)
        if "row_count" in fixed_assertions and len(expected_rows) != fixed_assertions["row_count"]:
            return False

        if "sum_column" in fixed_assertions:
            assertion = fixed_assertions["sum_column"]
            column_index = indexes.get(assertion["column"].casefold())
            if column_index is None:
                return False
            try:
                actual_sum = sum(
                    (cls._to_decimal(row[column_index]) for row in expected_rows),
                    Decimal("0"),
                )
            except ValueError:
                return False
            tolerance = cls._assertion_tolerance(assertion, default_tolerance)
            if not cls._value_matches(actual_sum, assertion["value"], tolerance):
                return False

        if "scalar" in fixed_assertions:
            assertion = fixed_assertions["scalar"]
            column_index = indexes.get(assertion["column"].casefold())
            if column_index is None or len(expected_rows) != 1:
                return False
            tolerance = cls._assertion_tolerance(assertion, default_tolerance)
            if not cls._value_matches(
                expected_rows[0][column_index], assertion["value"], tolerance
            ):
                return False

        return True

    @classmethod
    def _assertion_tolerance(
        cls, assertion: dict, default_tolerance: Decimal
    ) -> Decimal:
        if "absolute_tolerance" not in assertion:
            return default_tolerance
        return cls._to_tolerance(assertion["absolute_tolerance"])

    def _build_diff_samples(
        self,
        *,
        actual_columns: Sequence[str],
        expected_columns: Sequence[str],
        required_columns: Sequence[str],
        actual_rows: Sequence[Sequence[Any]],
        expected_rows: Sequence[Sequence[Any]],
        columns_matched: bool,
        values_matched: bool,
        tolerance: Decimal,
    ) -> List[Dict[str, Any]]:
        if self.max_diff_samples == 0:
            return []
        if not columns_matched:
            return [
                {
                    "actual_columns": list(actual_columns),
                    "expected_columns": list(expected_columns),
                    "required_columns": list(required_columns),
                }
            ]
        # 值集合已匹配时无需重复返回样本；顺序差异由 order_mismatch 单独表达。
        if values_matched:
            return []

        samples = []
        matched_expected = set()
        for actual in actual_rows:
            match = next(
                (
                    index
                    for index, expected in enumerate(expected_rows)
                    if index not in matched_expected
                    and self._row_matches(actual, expected, tolerance)
                ),
                None,
            )
            if match is None:
                samples.append({"actual": self._sample_row(actual), "expected": None})
            else:
                matched_expected.add(match)
            if len(samples) >= self.max_diff_samples:
                return samples

        for index, expected in enumerate(expected_rows):
            if index not in matched_expected:
                samples.append({"actual": None, "expected": self._sample_row(expected)})
            if len(samples) >= self.max_diff_samples:
                break
        return samples

    @classmethod
    def _sample_row(cls, row: Iterable[Any]) -> List[Any]:
        return [cls._sample_value(value) for value in row]

    @classmethod
    def _sample_value(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        return cls._normalize_non_number(value)
