"""比较 Agent 与黄金参考查询的结构化结果。"""

from collections import deque
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SUPPORTED_MODES = {"unordered", "ordered", "top_n", "scalar"}
MAX_SAMPLE_COLUMNS = 20
MAX_SAMPLE_STRING_LENGTH = 200
TRUNCATION_MARKER = "...[truncated]"
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
            mode, required_columns, _order_by, tolerance = self._validate_comparison(
                comparison, expected_columns
            )
            self._validate_fixed_assertions(fixed_assertions)

            actual_indexes = self._column_indexes(actual_columns)
            expected_indexes = self._column_indexes(expected_columns)
            required_keys = [column.casefold() for column in required_columns]
            # 黄金 case 通过 required_columns 锁定完整输出契约，额外列与缺少列都应失败。
            columns_matched = (
                set(actual_indexes) == set(required_keys)
                and set(expected_indexes) == set(required_keys)
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
            matching_complete = False
            unmatched_actual: List[int] = []
            unmatched_expected: List[int] = []
            if columns_matched:
                (
                    matching_complete,
                    unmatched_actual,
                    unmatched_expected,
                ) = self._multiset_match_result(
                    actual_projected, expected_projected, tolerance
                )
            values_matched = columns_matched and row_count_matched and matching_complete
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
                unmatched_actual=unmatched_actual,
                unmatched_expected=unmatched_expected,
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
    ) -> Tuple[str, List[str], List[str], Decimal]:
        if not isinstance(comparison, dict):
            raise ValueError("comparison must be a dict")

        mode = comparison.get("mode")
        if mode not in SUPPORTED_MODES:
            raise ValueError("unsupported comparison mode")

        required_columns = comparison.get("required_columns", expected_columns)
        if (
            not cls._is_sequence(required_columns)
            or not required_columns
            or not all(
                isinstance(column, str) and column for column in required_columns
            )
        ):
            raise ValueError("required_columns must contain strings")
        required_keys = [column.casefold() for column in required_columns]
        if len(required_keys) != len(set(required_keys)):
            raise ValueError("required_columns must be unique ignoring case")

        order_by = comparison.get("order_by")
        if mode in {"ordered", "top_n"}:
            if (
                not cls._is_sequence(order_by)
                or not order_by
                or not all(isinstance(column, str) and column for column in order_by)
            ):
                raise ValueError("ordered modes require order_by")
            order_keys = [column.casefold() for column in order_by]
            if len(order_keys) != len(set(order_keys)) or not set(order_keys).issubset(
                required_keys
            ):
                raise ValueError("order_by must reference required_columns")
        else:
            if "order_by" in comparison:
                raise ValueError("unordered and scalar modes do not accept order_by")
            order_by = []

        tolerance = cls._to_tolerance(comparison.get("absolute_tolerance", 0.001))
        return mode, list(required_columns), list(order_by), tolerance

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
            ):
                raise ValueError("malformed fixed assertion")
            value_is_valid = (
                cls._is_number(assertion["value"])
                if assertion_name == "sum_column"
                else cls._is_scalar_assertion_value(assertion["value"])
            )
            if not value_is_valid:
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
    def _multiset_match_result(
        cls,
        actual_rows: Sequence[Sequence[Any]],
        expected_rows: Sequence[Sequence[Any]],
        tolerance: Decimal,
    ) -> Tuple[bool, List[int], List[int]]:
        # 先按精确规范化键消除完全相同的行，常见的大量重复结果可在线性时间完成。
        expected_by_key: Dict[Tuple[Any, ...], deque[int]] = {}
        remaining_expected = set(range(len(expected_rows)))
        remaining_actual = []
        for expected_index, row in enumerate(expected_rows):
            key = cls._exact_row_key(row)
            if key is not None:
                expected_by_key.setdefault(key, deque()).append(expected_index)
        for actual_index, row in enumerate(actual_rows):
            key = cls._exact_row_key(row)
            matches = expected_by_key.get(key) if key is not None else None
            if matches:
                remaining_expected.remove(matches.popleft())
            else:
                remaining_actual.append(actual_index)

        remaining_expected_list = sorted(remaining_expected)
        # 容差会破坏普通哈希 Counter 的等价关系，只对精确消除后的剩余行做二分图匹配。
        candidates = [
            [
                expected_index
                for expected_index in remaining_expected_list
                if cls._row_matches(
                    actual_rows[actual_index],
                    expected_rows[expected_index],
                    tolerance,
                )
            ]
            for actual_index in remaining_actual
        ]
        matched_actual_by_expected: Dict[int, int] = {}
        matched_expected_by_actual: Dict[int, int] = {}

        for start_actual in range(len(remaining_actual)):
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
                continue

            expected_index = unmatched_expected
            while True:
                actual_index = parent_actual_by_expected[expected_index]
                previous_expected = matched_expected_by_actual.get(actual_index)
                matched_actual_by_expected[expected_index] = actual_index
                matched_expected_by_actual[actual_index] = expected_index
                if previous_expected is None:
                    break
                expected_index = previous_expected

        matched_actual_indexes = {
            remaining_actual[actual_position]
            for actual_position in matched_expected_by_actual
        }
        matched_expected_indexes = set(matched_actual_by_expected)
        unmatched_actual = [
            index for index in remaining_actual if index not in matched_actual_indexes
        ]
        unmatched_expected = [
            index
            for index in remaining_expected_list
            if index not in matched_expected_indexes
        ]
        return (
            not unmatched_actual and not unmatched_expected,
            unmatched_actual,
            unmatched_expected,
        )

    @classmethod
    def _exact_row_key(cls, row: Sequence[Any]) -> Optional[Tuple[Any, ...]]:
        keys = []
        for value in row:
            key = cls._exact_value_key(value)
            if key is None:
                return None
            keys.append(key)
        return tuple(keys)

    @classmethod
    def _exact_value_key(cls, value: Any) -> Optional[Tuple[Any, ...]]:
        if isinstance(value, bool):
            return ("bool", value)
        if cls._is_number(value):
            decimal_value = cls._finite_decimal_or_none(value)
            return None if decimal_value is None else ("number", decimal_value)
        normalized = cls._normalize_non_number(value)
        try:
            hash(normalized)
        except TypeError:
            return None
        return ("value", type(normalized).__name__, normalized)

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
        # Python 中 bool 是 int 的子类，这里显式隔离，避免 True == 1 隐藏类型错误。
        if isinstance(actual, bool) or isinstance(expected, bool):
            return (
                isinstance(actual, bool)
                and isinstance(expected, bool)
                and actual == expected
            )
        if cls._is_number(actual) and cls._is_number(expected):
            actual_decimal = cls._finite_decimal_or_none(actual)
            expected_decimal = cls._finite_decimal_or_none(expected)
            if actual_decimal is None or expected_decimal is None:
                return False
            return abs(actual_decimal - expected_decimal) <= tolerance
        return cls._normalize_non_number(actual) == cls._normalize_non_number(expected)

    @staticmethod
    def _normalize_non_number(value: Any) -> Any:
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        return value

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (Decimal, int, float)) and not isinstance(value, bool)

    @staticmethod
    def _is_scalar_assertion_value(value: Any) -> bool:
        return (
            isinstance(value, (Decimal, int, float, bool, str, datetime, date, time))
            or value is None
        )

    @classmethod
    def _finite_decimal_or_none(cls, value: Any) -> Optional[Decimal]:
        try:
            return cls._to_decimal(value)
        except ValueError:
            return None

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
        if (
            "row_count" in fixed_assertions
            and len(expected_rows) != fixed_assertions["row_count"]
        ):
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
        unmatched_actual: Sequence[int],
        unmatched_expected: Sequence[int],
    ) -> List[Dict[str, Any]]:
        if self.max_diff_samples == 0:
            return []
        if not columns_matched:
            return [
                {
                    "actual_columns": self._sample_columns(actual_columns),
                    "expected_columns": self._sample_columns(expected_columns),
                    "required_columns": self._sample_columns(required_columns),
                }
            ]
        # 值集合已匹配时无需重复返回样本；顺序差异由 order_mismatch 单独表达。
        if values_matched:
            return []

        samples = []
        # 直接复用主匹配得到的未匹配索引，避免诊断阶段的贪心算法制造虚假差异。
        for actual_index in unmatched_actual:
            samples.append(
                {"actual": self._sample_row(actual_rows[actual_index]), "expected": None}
            )
            if len(samples) >= self.max_diff_samples:
                return samples

        for expected_index in unmatched_expected:
            samples.append(
                {
                    "actual": None,
                    "expected": self._sample_row(expected_rows[expected_index]),
                }
            )
            if len(samples) >= self.max_diff_samples:
                break
        return samples

    @classmethod
    def _sample_row(cls, row: Iterable[Any]) -> List[Any]:
        values = list(row)
        sampled = [cls._sample_value(value) for value in values[:MAX_SAMPLE_COLUMNS]]
        if len(values) > MAX_SAMPLE_COLUMNS:
            sampled[-1] = TRUNCATION_MARKER
        return sampled

    @classmethod
    def _sample_columns(cls, columns: Sequence[str]) -> List[str]:
        sampled = [cls._sample_string(column) for column in columns[:MAX_SAMPLE_COLUMNS]]
        if len(columns) > MAX_SAMPLE_COLUMNS:
            sampled[-1] = TRUNCATION_MARKER
        return sampled

    @classmethod
    def _sample_value(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        normalized = cls._normalize_non_number(value)
        if isinstance(normalized, str):
            return cls._sample_string(normalized)
        return normalized

    @staticmethod
    def _sample_string(value: str) -> str:
        if len(value) <= MAX_SAMPLE_STRING_LENGTH:
            return value
        return value[:MAX_SAMPLE_STRING_LENGTH] + TRUNCATION_MARKER
