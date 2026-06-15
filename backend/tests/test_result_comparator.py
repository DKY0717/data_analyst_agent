"""ResultComparator 的确定性契约测试。"""

from datetime import date, datetime, time
from decimal import Decimal
from time import perf_counter

import pytest

from evaluation.result_comparator import ResultComparator


RESULT_FIELDS = {
    "columns_matched",
    "row_count_matched",
    "values_matched",
    "order_matched",
    "fixed_assertions_matched",
    "result_correct",
    "failure_types",
    "diff_samples",
}


@pytest.fixture
def comparator():
    return ResultComparator()


def compare(comparator, actual, expected, mode="unordered", **comparison):
    """用统一的 required_columns 构造最小比较契约，减少测试噪声。"""
    required_columns = comparison.pop("required_columns", expected.get("columns", []))
    if mode in {"ordered", "top_n"} and "order_by" not in comparison:
        comparison["order_by"] = required_columns
    return comparator.compare(
        actual=actual,
        expected=expected,
        comparison={
            "mode": mode,
            "required_columns": required_columns,
            **comparison,
        },
    )


def test_scalar_numbers_match_within_absolute_tolerance(comparator):
    result = compare(
        comparator,
        actual={"columns": ["rate"], "rows": [[Decimal("0.5004")]]},
        expected={"columns": ["rate"], "rows": [[0.5]]},
        mode="scalar",
        absolute_tolerance=0.001,
    )

    assert set(result) == RESULT_FIELDS
    assert result["result_correct"] is True
    assert result["failure_types"] == []


@pytest.mark.parametrize(
    ("actual_value", "expected_value"),
    [
        (1, 1.0009),
        (Decimal("2.0009"), 2),
        (3.0009, Decimal("3")),
    ],
)
def test_decimal_float_and_int_use_absolute_tolerance(
    comparator, actual_value, expected_value
):
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": [[actual_value]]},
        expected={"columns": ["value"], "rows": [[expected_value]]},
        mode="scalar",
        absolute_tolerance=0.001,
    )

    assert result["result_correct"] is True


def test_dates_and_times_are_compared_as_iso_strings(comparator):
    result = compare(
        comparator,
        actual={
            "columns": ["day", "at", "created_at"],
            "rows": [[date(2026, 6, 15), time(8, 30), datetime(2026, 6, 15, 8, 30)]],
        },
        expected={
            "columns": ["day", "at", "created_at"],
            "rows": [["2026-06-15", "08:30:00", "2026-06-15T08:30:00"]],
        },
    )

    assert result["result_correct"] is True


def test_column_names_are_case_insensitive_and_rows_are_projected_by_name(comparator):
    result = compare(
        comparator,
        actual={"columns": ["SALES", "Region"], "rows": [[10, "华东"]]},
        expected={"columns": ["region", "sales"], "rows": [["华东", 10]]},
        required_columns=["REGION", "sales"],
    )

    assert result["columns_matched"] is True
    assert result["result_correct"] is True


def test_column_names_do_not_use_semantic_guessing(comparator):
    result = compare(
        comparator,
        actual={"columns": ["amount"], "rows": [[10]]},
        expected={"columns": ["sales_amount"], "rows": [[10]]},
        required_columns=["sales_amount"],
    )

    assert result["columns_matched"] is False
    assert result["result_correct"] is False
    assert result["failure_types"] == ["column_mismatch"]


@pytest.mark.parametrize(
    ("actual_columns", "expected_columns"),
    [
        (["value", "extra"], ["value"]),
        (["value"], ["value", "extra"]),
        (["other"], ["value"]),
    ],
)
def test_columns_must_exactly_match_required_columns(
    comparator, actual_columns, expected_columns
):
    result = compare(
        comparator,
        actual={"columns": actual_columns, "rows": [[1] * len(actual_columns)]},
        expected={"columns": expected_columns, "rows": [[1] * len(expected_columns)]},
        required_columns=["value"],
    )

    assert result["columns_matched"] is False
    assert result["failure_types"] == ["column_mismatch"]


@pytest.mark.parametrize(
    "comparison",
    [
        {"mode": "unordered", "required_columns": []},
        {"mode": "unordered", "required_columns": "value"},
        {"mode": "ordered", "required_columns": ["value"]},
        {"mode": "top_n", "required_columns": ["value"], "order_by": []},
        {"mode": "ordered", "required_columns": ["value"], "order_by": "value"},
        {"mode": "ordered", "required_columns": ["value"], "order_by": ["missing"]},
        {"mode": "unordered", "required_columns": ["value"], "order_by": ["value"]},
        {"mode": "scalar", "required_columns": ["value"], "order_by": ["value"]},
    ],
)
def test_required_columns_and_order_by_contracts_fail_stably(comparator, comparison):
    result = comparator.compare(
        {"columns": ["value"], "rows": [[1]]},
        {"columns": ["value"], "rows": [[1]]},
        comparison,
    )

    assert result["failure_types"] == ["unexpected_error"]


def test_unordered_ignores_order_but_preserves_duplicate_row_differences(comparator):
    matched = compare(
        comparator,
        actual={"columns": ["name"], "rows": [["b"], ["a"], ["a"]]},
        expected={"columns": ["name"], "rows": [["a"], ["b"], ["a"]]},
    )
    mismatched = compare(
        comparator,
        actual={"columns": ["name"], "rows": [["a"], ["b"], ["b"]]},
        expected={"columns": ["name"], "rows": [["a"], ["a"], ["b"]]},
    )

    assert matched["result_correct"] is True
    assert mismatched["row_count_matched"] is True
    assert mismatched["values_matched"] is False
    assert mismatched["failure_types"] == ["value_mismatch"]


def test_unordered_eliminates_limit_sized_exact_duplicates_before_tolerance_matching(
    comparator,
):
    rows = [["same"]] * 1000

    started_at = perf_counter()
    result = compare(
        comparator,
        actual={"columns": ["name"], "rows": rows},
        expected={"columns": ["name"], "rows": list(reversed(rows))},
    )
    elapsed = perf_counter() - started_at

    assert result["result_correct"] is True
    # 完全相同行应走精确键消除；宽松上限用于防止退化回平方级匹配，同时避免 CI 抖动。
    assert elapsed < 1.0


@pytest.mark.parametrize("mode", ["ordered", "top_n"])
def test_ordered_modes_compare_rows_in_sequence(comparator, mode):
    result = compare(
        comparator,
        actual={"columns": ["name"], "rows": [["b"], ["a"]]},
        expected={"columns": ["name"], "rows": [["a"], ["b"]]},
        mode=mode,
    )

    assert result["values_matched"] is True
    assert result["order_matched"] is False
    assert result["result_correct"] is False
    assert result["failure_types"] == ["order_mismatch"]


def test_top_n_requires_same_row_count(comparator):
    result = compare(
        comparator,
        actual={"columns": ["name"], "rows": [["a"]]},
        expected={"columns": ["name"], "rows": [["a"], ["b"]]},
        mode="top_n",
    )

    assert result["row_count_matched"] is False
    assert result["values_matched"] is False
    assert result["order_matched"] is False
    assert result["failure_types"] == [
        "row_count_mismatch",
        "value_mismatch",
        "order_mismatch",
    ]


@pytest.mark.parametrize("actual_rows", [[], [[1], [1]]])
def test_scalar_requires_exactly_one_row(comparator, actual_rows):
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": actual_rows},
        expected={"columns": ["value"], "rows": [[1]]},
        mode="scalar",
    )

    assert result["row_count_matched"] is False
    assert result["result_correct"] is False
    assert "row_count_mismatch" in result["failure_types"]


@pytest.mark.parametrize(
    ("actual_value", "expected_value"),
    [(True, 1), (False, 0), (1, True), (0, False)],
)
def test_bool_never_matches_numbers(comparator, actual_value, expected_value):
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": [[actual_value]]},
        expected={"columns": ["value"], "rows": [[expected_value]]},
        mode="scalar",
    )

    assert result["columns_matched"] is True
    assert result["row_count_matched"] is True
    assert result["values_matched"] is False
    assert result["failure_types"] == ["value_mismatch"]


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_value_mismatches_without_losing_structure(
    comparator, non_finite
):
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": [[non_finite]]},
        expected={"columns": ["value"], "rows": [[1.0]]},
        mode="scalar",
    )

    assert result["columns_matched"] is True
    assert result["row_count_matched"] is True
    assert result["values_matched"] is False
    assert result["fixed_assertions_matched"] is True
    assert result["failure_types"] == ["value_mismatch"]


def test_fixed_assertions_support_row_count_and_sum_column(comparator):
    expected = {"columns": ["name", "amount"], "rows": [["a", 1], ["b", 2]]}
    result = comparator.compare(
        actual=expected,
        expected=expected,
        comparison={
            "mode": "unordered",
            "required_columns": ["name", "amount"],
            "absolute_tolerance": 0.001,
        },
        fixed_assertions={
            "row_count": 2,
            "sum_column": {"column": "amount", "value": Decimal("3.0004")},
        },
    )

    assert result["fixed_assertions_matched"] is True
    assert result["result_correct"] is True


@pytest.mark.parametrize(
    "fixed_assertions",
    [
        {"row_count": 3},
        {"sum_column": {"column": "amount", "value": 4}},
        {"scalar": {"column": "amount", "value": 2}},
    ],
)
def test_each_fixed_assertion_reports_stable_failure(comparator, fixed_assertions):
    expected = {"columns": ["amount"], "rows": [[1], [2]]}
    result = comparator.compare(
        actual=expected,
        expected=expected,
        comparison={"mode": "unordered", "required_columns": ["amount"]},
        fixed_assertions=fixed_assertions,
    )

    assert result["fixed_assertions_matched"] is False
    assert result["result_correct"] is False
    assert result["failure_types"] == ["fixed_assertion_failed"]


def test_scalar_fixed_assertion_uses_its_own_tolerance(comparator):
    expected = {"columns": ["rate"], "rows": [[Decimal("0.5004")]]}
    result = comparator.compare(
        actual=expected,
        expected=expected,
        comparison={"mode": "scalar", "required_columns": ["rate"]},
        fixed_assertions={
            "scalar": {
                "column": "RATE",
                "value": 0.5,
                "absolute_tolerance": 0.001,
            }
        },
    )

    assert result["fixed_assertions_matched"] is True
    assert result["result_correct"] is True


@pytest.mark.parametrize(
    ("expected_value", "asserted_value"),
    [(True, 1), (1, True), (False, 0), (0, False)],
)
def test_bool_never_matches_numbers_in_fixed_assertions(
    comparator, expected_value, asserted_value
):
    expected = {"columns": ["value"], "rows": [[expected_value]]}
    result = comparator.compare(
        actual=expected,
        expected=expected,
        comparison={"mode": "scalar", "required_columns": ["value"]},
        fixed_assertions={"scalar": {"column": "value", "value": asserted_value}},
    )

    assert result["fixed_assertions_matched"] is False
    assert result["failure_types"] == ["fixed_assertion_failed"]


@pytest.mark.parametrize("configured_limit", [5, 100])
def test_comparator_reports_stable_failure_types_and_limits_samples(configured_limit):
    comparator = ResultComparator(max_diff_samples=configured_limit)
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": [[value] for value in range(10)]},
        expected={"columns": ["value"], "rows": [[value] for value in range(10, 20)]},
    )

    assert result["failure_types"] == ["value_mismatch"]
    assert len(result["diff_samples"]) == 5


def test_diff_samples_limit_columns_and_truncate_large_strings(comparator):
    columns = [f"column_{index}_" + ("x" * 1000) for index in range(100)]
    huge_value = "v" * 1_000_000
    result = compare(
        comparator,
        actual={"columns": columns, "rows": [[huge_value] * len(columns)]},
        expected={"columns": columns, "rows": [["different"] * len(columns)]},
    )

    assert len(result["diff_samples"]) <= 5
    for sample in result["diff_samples"]:
        for row in (sample.get("actual"), sample.get("expected")):
            if row is not None:
                assert len(row) <= 20
                assert all(len(str(value)) <= 220 for value in row)
                assert any("[truncated]" in str(value) for value in row)


def test_column_diff_samples_are_limited_and_truncated(comparator):
    actual_columns = [f"actual_{index}_" + ("a" * 1000) for index in range(100)]
    expected_columns = [f"expected_{index}_" + ("e" * 1000) for index in range(100)]
    result = comparator.compare(
        actual={"columns": actual_columns, "rows": []},
        expected={"columns": expected_columns, "rows": []},
        comparison={"mode": "unordered", "required_columns": expected_columns},
    )

    sample = result["diff_samples"][0]
    assert all(len(columns) <= 20 for columns in sample.values())
    assert all(
        len(column) <= 220 and "[truncated]" in column
        for columns in sample.values()
        for column in columns
    )


def test_diff_samples_reuse_tolerance_matching_without_false_differences(comparator):
    result = compare(
        comparator,
        actual={"columns": ["value"], "rows": [[0.1], [0.0], [9.0]]},
        expected={"columns": ["value"], "rows": [[0.0], [0.2], [10.0]]},
        absolute_tolerance=0.11,
    )

    assert result["failure_types"] == ["value_mismatch"]
    assert result["diff_samples"] == [
        {"actual": [9.0], "expected": None},
        {"actual": None, "expected": [10.0]},
    ]


def test_failure_types_follow_stable_order(comparator):
    result = comparator.compare(
        actual={"columns": ["value"], "rows": [[2], [3]]},
        expected={"columns": ["value"], "rows": [[1]]},
        comparison={
            "mode": "ordered",
            "required_columns": ["value"],
            "order_by": ["value"],
        },
        fixed_assertions={"row_count": 2},
    )

    assert result["failure_types"] == [
        "row_count_mismatch",
        "value_mismatch",
        "order_mismatch",
        "fixed_assertion_failed",
    ]


@pytest.mark.parametrize(
    ("actual", "expected", "comparison", "fixed_assertions"),
    [
        (None, {"columns": [], "rows": []}, {"mode": "unordered"}, None),
        ({"columns": "value", "rows": []}, {"columns": [], "rows": []}, {"mode": "unordered"}, None),
        ({"columns": ["value"], "rows": "bad"}, {"columns": ["value"], "rows": []}, {"mode": "unordered"}, None),
        ({"columns": ["value"], "rows": [[1, 2]]}, {"columns": ["value"], "rows": [[1]]}, {"mode": "unordered"}, None),
        ({"columns": ["value", "VALUE"], "rows": [[1, 1]]}, {"columns": ["value"], "rows": [[1]]}, {"mode": "unordered"}, None),
        ({"columns": [], "rows": []}, {"columns": [], "rows": []}, {"mode": "unsupported"}, None),
        ({"columns": [], "rows": []}, {"columns": [], "rows": []}, {"mode": "unordered", "absolute_tolerance": -1}, None),
        ({"columns": [], "rows": []}, {"columns": [], "rows": []}, {"mode": "unordered"}, {"unknown": 1}),
    ],
)
def test_malformed_inputs_and_unsupported_modes_fail_stably(
    comparator, actual, expected, comparison, fixed_assertions
):
    result = comparator.compare(actual, expected, comparison, fixed_assertions)

    assert set(result) == RESULT_FIELDS
    assert result == {
        "columns_matched": False,
        "row_count_matched": False,
        "values_matched": False,
        "order_matched": False,
        "fixed_assertions_matched": False,
        "result_correct": False,
        "failure_types": ["unexpected_error"],
        "diff_samples": [],
    }
