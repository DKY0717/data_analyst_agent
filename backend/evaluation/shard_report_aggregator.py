"""严格校验并汇总真实模型评测分片证据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from app.utils.logger import logger
from evaluation.correctness_report_writer import CorrectnessReportWriter
from evaluation.evaluator import EvaluationRunner
from evaluation.repair_evaluator import RepairEvaluationRunner
from evaluation.repair_report_writer import RepairReportWriter
from evaluation.report_writer import ReportWriter
from evaluation.result_correctness_evaluator import ResultCorrectnessEvaluator
from evaluation.shard_support import AtomicCheckpointWriter, case_file_sha256


SummarizeResults = Callable[[list[dict[str, Any]]], Mapping[str, Any]]


class ShardAggregationError(ValueError):
    """携带脱敏诊断的严格汇总失败，不暴露底层解析器原始异常。"""

    def __init__(self, diagnostics: dict[str, Any]):
        super().__init__("真实模型评测分片证据不完整或不一致")
        self.diagnostics = diagnostics


class ShardReportAggregator:
    """只接受同一身份、完整覆盖当前 case pack 的分片全集。"""

    def __init__(
        self,
        *,
        suite: str,
        case_file: str | Path,
        shard_count: int,
        expected_head_sha: str,
        expected_provider: str,
        expected_model: str,
        summarize: SummarizeResults,
    ):
        if shard_count <= 0:
            raise ValueError("分片总数必须大于 0")
        self.suite = suite
        self.case_file = Path(case_file)
        self.shard_count = shard_count
        self.expected_head_sha = expected_head_sha
        self.expected_provider = expected_provider
        self.expected_model = expected_model
        self.summarize = summarize
        self.case_ids = self._load_case_ids()
        self.case_hash = case_file_sha256(self.case_file)

    def _load_case_ids(self) -> list[str]:
        """case YAML 是覆盖范围的唯一权威来源，文件名和分片自报 ID 都不可信。"""
        with self.case_file.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file)
        cases = payload.get("cases") if isinstance(payload, dict) else None
        if not isinstance(cases, list):
            raise ValueError("评测 case 文件必须包含 cases 列表")

        case_ids: list[str] = []
        seen: set[str] = set()
        for case in cases:
            case_id = case.get("id") if isinstance(case, dict) else None
            if not isinstance(case_id, str) or not case_id.strip():
                raise ValueError("每条评测 case 必须提供非空字符串 ID")
            if case_id in seen:
                raise ValueError(f"评测 case ID 重复: {case_id}")
            seen.add(case_id)
            case_ids.append(case_id)
        return case_ids

    def aggregate(self, input_dir: str | Path) -> dict[str, Any]:
        """先完成全部身份与覆盖校验，再生成没有 shard 元数据的正式全集报告。"""
        errors: list[dict[str, Any]] = []
        checkpoints: dict[int, dict[str, Any]] = {}
        input_path = Path(input_dir)

        for report_path in sorted(input_path.rglob("*.json")) if input_path.exists() else []:
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                self._add_error(errors, "invalid_json", files=[report_path.name])
                continue

            # 下载目录可能同时包含 run metadata；只有显式 shard 契约的 JSON 才是候选证据。
            if not isinstance(payload, dict) or not isinstance(payload.get("shard"), dict):
                continue
            metadata = payload["shard"]
            shard_index = metadata.get("shard_index")
            if type(shard_index) is not int or not 0 <= shard_index < self.shard_count:
                self._add_error(errors, "invalid_shard_metadata")
                continue
            if shard_index in checkpoints:
                self._add_error(errors, "duplicate_shard_index", shard_indices=[shard_index])
                continue
            checkpoints[shard_index] = payload

        missing_shard_indices = [
            index for index in range(self.shard_count) if index not in checkpoints
        ]
        if missing_shard_indices:
            self._add_error(
                errors,
                "missing_shard_indices",
                shard_indices=missing_shard_indices,
            )

        results_by_id: dict[str, dict[str, Any]] = {}
        duplicate_case_ids: set[str] = set()
        for shard_index, payload in sorted(checkpoints.items()):
            self._validate_checkpoint(
                shard_index,
                payload,
                errors,
                results_by_id,
                duplicate_case_ids,
            )

        expected_ids = set(self.case_ids)
        actual_ids = set(results_by_id)
        missing_case_ids = [case_id for case_id in self.case_ids if case_id not in actual_ids]
        unknown_case_ids = sorted(actual_ids - expected_ids)
        if missing_case_ids or unknown_case_ids or duplicate_case_ids:
            self._add_error(
                errors,
                "case_coverage_mismatch",
                missing_case_ids=missing_case_ids,
                unknown_case_ids=unknown_case_ids,
                duplicate_case_ids=sorted(duplicate_case_ids),
            )

        if errors:
            raise ShardAggregationError(
                {
                    "status": "failed",
                    "suite": self.suite,
                    "errors": errors,
                    "missing_shard_indices": missing_shard_indices,
                    "missing_case_ids": missing_case_ids,
                    "unknown_case_ids": unknown_case_ids,
                    "duplicate_case_ids": sorted(duplicate_case_ids),
                }
            )

        # 按权威 YAML 顺序恢复结果，不能沿用 artifact 下载顺序或分片 summary。
        ordered_results = [results_by_id[case_id] for case_id in self.case_ids]
        try:
            summary = dict(self.summarize(ordered_results))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            # case ID 完整不等于结果字段完整；summary 契约错误也必须留下稳定诊断。
            raise ShardAggregationError(
                {
                    "status": "failed",
                    "suite": self.suite,
                    "errors": [{"code": "invalid_result_contract", "stage": "summary"}],
                    "missing_shard_indices": [],
                    "missing_case_ids": [],
                    "unknown_case_ids": [],
                    "duplicate_case_ids": [],
                }
            ) from None
        return {
            "summary": summary,
            "results": ordered_results,
        }

    def _validate_checkpoint(
        self,
        shard_index: int,
        payload: dict[str, Any],
        errors: list[dict[str, Any]],
        results_by_id: dict[str, dict[str, Any]],
        duplicate_case_ids: set[str],
    ) -> None:
        metadata = payload["shard"]
        expected_case_ids = self.case_ids[shard_index :: self.shard_count]
        expected_metadata = {
            "schema_version": 1,
            "suite": self.suite,
            "head_sha": self.expected_head_sha,
            "provider": self.expected_provider,
            "model": self.expected_model,
            "case_file_sha256": self.case_hash,
            "shard_index": shard_index,
            "shard_count": self.shard_count,
        }
        mismatched_fields = [
            field
            for field, expected_value in expected_metadata.items()
            if metadata.get(field) != expected_value
        ]
        if mismatched_fields:
            self._add_error(
                errors,
                "metadata_mismatch",
                shard_indices=[shard_index],
                fields=sorted(mismatched_fields),
            )

        if metadata.get("complete") is not True:
            self._add_error(errors, "incomplete_shard", shard_indices=[shard_index])

        completed_case_ids = metadata.get("completed_case_ids")
        declared_expected_ids = metadata.get("expected_case_ids")
        results = payload.get("results")
        result_ids = (
            [result.get("case_id") for result in results if isinstance(result, dict)]
            if isinstance(results, list)
            else None
        )
        contract_valid = (
            declared_expected_ids == expected_case_ids
            and completed_case_ids == expected_case_ids
            and isinstance(results, list)
            and len(result_ids or []) == len(results)
            and result_ids == expected_case_ids
        )
        if not contract_valid:
            self._add_error(
                errors,
                "case_coverage_mismatch",
                shard_indices=[shard_index],
            )

        if not isinstance(results, list):
            return
        for result in results:
            if not isinstance(result, dict):
                continue
            case_id = result.get("case_id")
            if not isinstance(case_id, str):
                continue
            if case_id in results_by_id:
                duplicate_case_ids.add(case_id)
                continue
            # 拷贝结果，避免汇总排序或 writer 过滤时修改原始 checkpoint 对象。
            results_by_id[case_id] = dict(result)

    @staticmethod
    def _add_error(
        errors: list[dict[str, Any]], code: str, **details: Any
    ) -> None:
        """错误只使用稳定 code 和有限标识符，避免复制解析器或供应商异常文本。"""
        entry = {"code": code, **details}
        if entry not in errors:
            errors.append(entry)


async def _unused_agent_runner(_question: str) -> dict[str, Any]:
    """汇总只复用 summary 公式；若意外触发 Agent，必须立即失败。"""
    raise RuntimeError("汇总阶段不得调用 Agent")


def _suite_services(
    suite: str, output_dir: str | Path
) -> tuple[SummarizeResults, Any]:
    """集中绑定既有 summary 与正式 writer，避免复制三套质量指标公式。"""
    if suite == "nl2sql":
        runner = EvaluationRunner(agent_runner=_unused_agent_runner)
        return runner.summarize_results, ReportWriter(output_dir=output_dir)
    if suite == "repair":
        runner = RepairEvaluationRunner()
        return runner.summarize_results, RepairReportWriter(output_dir=output_dir)
    if suite == "correctness":
        runner = ResultCorrectnessEvaluator(agent_runner=_unused_agent_runner)
        return runner.summarize_results, CorrectnessReportWriter(output_dir=output_dir)
    raise ValueError("不支持的评测 suite")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="严格合并真实模型评测分片")
    parser.add_argument("--suite", choices=("nl2sql", "repair", "correctness"), required=True)
    parser.add_argument("--case-file", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--expected-provider", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--diagnostics-output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    diagnostics_writer = AtomicCheckpointWriter(args.diagnostics_output)
    try:
        summarize, writer = _suite_services(args.suite, args.output_dir)
        aggregator = ShardReportAggregator(
            suite=args.suite,
            case_file=args.case_file,
            shard_count=args.shard_count,
            expected_head_sha=args.expected_head_sha,
            expected_provider=args.expected_provider,
            expected_model=args.expected_model,
            summarize=summarize,
        )
        report = aggregator.aggregate(args.input_dir)
        paths = writer.write(report)
        diagnostics_writer.write(
            {
                "status": "passed",
                "suite": args.suite,
                "total_cases": report["summary"].get("total_cases", 0),
            }
        )
        print(f"Aggregated {args.suite} report: {paths['json']}")
        return 0
    except ShardAggregationError as exc:
        diagnostics_writer.write(exc.diagnostics)
        logger.error("评测分片汇总失败，suite=%s", args.suite)
        return 2
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        # 初始化或正式 writer 失败同样只记录异常类型，诊断中不复制文件内容。
        diagnostics_writer.write(
            {
                "status": "failed",
                "suite": args.suite,
                "errors": [
                    {"code": "aggregation_initialization_error", "error_type": type(exc).__name__}
                ],
            }
        )
        logger.error(
            "评测分片汇总初始化失败，suite=%s，异常类型=%s",
            args.suite,
            type(exc).__name__,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
