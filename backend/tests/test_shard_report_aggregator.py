"""真实模型分片报告严格汇总测试。"""

import json
from copy import deepcopy

import pytest

from evaluation.shard_report_aggregator import (
    ShardAggregationError,
    ShardReportAggregator,
    main,
)
from evaluation.shard_support import case_file_sha256


HEAD_SHA = "abc123"
PROVIDER = "mimo"
MODEL = "mimo-v2.5-pro"


def write_case_file(tmp_path, count=5):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text(
        "cases:\n"
        + "".join(
            f"  - id: case_{index}\n    question: 问题 {index}\n"
            for index in range(count)
        ),
        encoding="utf-8",
    )
    return case_file


def checkpoint_payload(case_file, *, shard_index, shard_count=2, complete=True):
    all_ids = [f"case_{index}" for index in range(5)]
    expected_ids = [
        case_id for position, case_id in enumerate(all_ids) if position % shard_count == shard_index
    ]
    completed_ids = expected_ids if complete else expected_ids[:-1]
    return {
        "shard": {
            "schema_version": 1,
            "suite": "nl2sql",
            "head_sha": HEAD_SHA,
            "provider": PROVIDER,
            "model": MODEL,
            "case_file_sha256": case_file_sha256(case_file),
            "shard_index": shard_index,
            "shard_count": shard_count,
            "expected_case_ids": expected_ids,
            "completed_case_ids": completed_ids,
            "complete": complete,
        },
        # 分片 summary 故意写错，证明汇总器只信任全集 results 后的重新计算。
        "summary": {"total_cases": 999},
        "results": [
            {"case_id": case_id, "passed": True}
            for case_id in completed_ids
        ],
    }


def write_checkpoints(tmp_path, case_file, shard_count=2):
    input_dir = tmp_path / "shards"
    input_dir.mkdir()
    for shard_index in range(shard_count):
        payload = checkpoint_payload(
            case_file,
            shard_index=shard_index,
            shard_count=shard_count,
        )
        (input_dir / f"checkpoint-{shard_index}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
    return input_dir


def make_aggregator(case_file, shard_count=2):
    return ShardReportAggregator(
        suite="nl2sql",
        case_file=case_file,
        shard_count=shard_count,
        expected_head_sha=HEAD_SHA,
        expected_provider=PROVIDER,
        expected_model=MODEL,
        summarize=lambda results: {
            "total_cases": len(results),
            "pass_rate": sum(item["passed"] is True for item in results) / len(results),
        },
    )


def error_codes(exc_info) -> set[str]:
    return {item["code"] for item in exc_info.value.diagnostics["errors"]}


def test_complete_shards_restore_case_order_and_recompute_summary(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)

    report = make_aggregator(case_file).aggregate(input_dir)

    assert [item["case_id"] for item in report["results"]] == [
        "case_0",
        "case_1",
        "case_2",
        "case_3",
        "case_4",
    ]
    assert report["summary"] == {"total_cases": 5, "pass_rate": 1.0}
    assert "shard" not in report


def test_missing_shard_fails_closed_with_stable_diagnostics(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    (input_dir / "checkpoint-1.json").unlink()

    with pytest.raises(ShardAggregationError) as exc_info:
        make_aggregator(case_file).aggregate(input_dir)

    assert "missing_shard_indices" in error_codes(exc_info)
    assert exc_info.value.diagnostics["missing_case_ids"] == ["case_1", "case_3"]


def test_duplicate_shard_index_is_rejected_even_when_files_have_different_names(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    duplicate = (input_dir / "checkpoint-0.json").read_text(encoding="utf-8")
    (input_dir / "copied-evidence.json").write_text(duplicate, encoding="utf-8")

    with pytest.raises(ShardAggregationError) as exc_info:
        make_aggregator(case_file).aggregate(input_dir)

    assert "duplicate_shard_index" in error_codes(exc_info)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda payload: payload["shard"].update(complete=False), "incomplete_shard"),
        (lambda payload: payload["shard"].update(model="other-model"), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(head_sha="other-sha"), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(provider="qwen"), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(case_file_sha256="bad"), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(schema_version=2), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(suite="repair"), "metadata_mismatch"),
        (lambda payload: payload["shard"].update(shard_count=3), "metadata_mismatch"),
    ],
)
def test_incomplete_or_mismatched_metadata_is_rejected(tmp_path, mutation, expected_code):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    checkpoint = input_dir / "checkpoint-0.json"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    mutation(payload)
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ShardAggregationError) as exc_info:
        make_aggregator(case_file).aggregate(input_dir)

    assert expected_code in error_codes(exc_info)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["shard"].update(expected_case_ids=["case_0"]),
        lambda payload: payload["shard"].update(completed_case_ids=["case_0"]),
        lambda payload: payload["results"].append({"case_id": "unknown", "passed": True}),
        lambda payload: payload["results"].__setitem__(0, {"case_id": "case_2", "passed": True}),
    ],
)
def test_case_contract_tampering_is_rejected(tmp_path, mutate):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    checkpoint = input_dir / "checkpoint-0.json"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    mutate(payload)
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ShardAggregationError) as exc_info:
        make_aggregator(case_file).aggregate(input_dir)

    assert "case_coverage_mismatch" in error_codes(exc_info)


def test_malformed_json_is_rejected_without_copying_parser_error(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    (input_dir / "broken.json").write_text('{"secret":', encoding="utf-8")

    with pytest.raises(ShardAggregationError) as exc_info:
        make_aggregator(case_file).aggregate(input_dir)

    assert "invalid_json" in error_codes(exc_info)
    assert "secret" not in json.dumps(exc_info.value.diagnostics)


def test_truncated_result_contract_becomes_stable_diagnostic(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    aggregator = ShardReportAggregator(
        suite="nl2sql",
        case_file=case_file,
        shard_count=2,
        expected_head_sha=HEAD_SHA,
        expected_provider=PROVIDER,
        expected_model=MODEL,
        summarize=lambda results: {"required": results[0]["missing_field"]},
    )

    with pytest.raises(ShardAggregationError) as exc_info:
        aggregator.aggregate(input_dir)

    assert "invalid_result_contract" in error_codes(exc_info)


def test_cli_failure_writes_diagnostics_and_no_formal_report(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    (input_dir / "checkpoint-1.json").unlink()
    output_dir = tmp_path / "merged"
    diagnostics = output_dir / "nl2sql-merge-diagnostics.json"

    exit_code = main(
        [
            "--suite",
            "nl2sql",
            "--case-file",
            str(case_file),
            "--input-dir",
            str(input_dir),
            "--expected-head-sha",
            HEAD_SHA,
            "--expected-provider",
            PROVIDER,
            "--expected-model",
            MODEL,
            "--shard-count",
            "2",
            "--output-dir",
            str(output_dir),
            "--diagnostics-output",
            str(diagnostics),
        ]
    )

    assert exit_code == 2
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["suite"] == "nl2sql"
    assert "missing_shard_indices" in {item["code"] for item in payload["errors"]}
    assert list(output_dir.glob("nl2sql-evaluation-*.json")) == []


def test_cli_complete_correctness_shard_writes_formal_report(tmp_path):
    case_file = tmp_path / "golden.yaml"
    case_file.write_text(
        "cases:\n  - id: golden_0\n    question: 测试\n",
        encoding="utf-8",
    )
    input_dir = tmp_path / "correctness-shards"
    input_dir.mkdir()
    result = {
        "case_id": "golden_0",
        "question": "测试",
        "category": "business_metric",
        "agent_sql": "",
        "agent_execution_success": False,
        "reference_guard_passed": False,
        "reference_execution_success": False,
        "columns_matched": False,
        "values_matched": False,
        "order_matched": False,
        "fixed_assertions_matched": False,
        "result_correct": False,
        "failure_type": "agent_execution_failed",
        "comparison_failure_types": [],
        "diff_samples": [],
    }
    payload = {
        "shard": {
            "schema_version": 1,
            "suite": "correctness",
            "head_sha": HEAD_SHA,
            "provider": PROVIDER,
            "model": MODEL,
            "case_file_sha256": case_file_sha256(case_file),
            "shard_index": 0,
            "shard_count": 1,
            "expected_case_ids": ["golden_0"],
            "completed_case_ids": ["golden_0"],
            "complete": True,
        },
        "summary": {"total_cases": 999},
        "results": [result],
    }
    (input_dir / "checkpoint.json").write_text(json.dumps(payload), encoding="utf-8")
    output_dir = tmp_path / "merged"
    diagnostics = output_dir / "diagnostics.json"

    exit_code = main(
        [
            "--suite",
            "correctness",
            "--case-file",
            str(case_file),
            "--input-dir",
            str(input_dir),
            "--expected-head-sha",
            HEAD_SHA,
            "--expected-provider",
            PROVIDER,
            "--expected-model",
            MODEL,
            "--shard-count",
            "1",
            "--output-dir",
            str(output_dir),
            "--diagnostics-output",
            str(diagnostics),
        ]
    )

    assert exit_code == 0
    report_paths = list(output_dir.glob("result-correctness-evaluation-*.json"))
    assert len(report_paths) == 1
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))
    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["result_correctness_rate"] == 0
    assert json.loads(diagnostics.read_text(encoding="utf-8"))["status"] == "passed"


def test_aggregator_does_not_mutate_loaded_result_objects(tmp_path):
    case_file = write_case_file(tmp_path)
    input_dir = write_checkpoints(tmp_path, case_file)
    original = json.loads((input_dir / "checkpoint-0.json").read_text(encoding="utf-8"))
    before = deepcopy(original["results"])

    make_aggregator(case_file).aggregate(input_dir)

    assert original["results"] == before
