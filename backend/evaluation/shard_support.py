"""真实模型评测的确定性分片与增量 checkpoint 基础组件。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence


Case = Mapping[str, Any]
CaseResult = Mapping[str, Any]
EvaluateCase = Callable[[Case], Awaitable[CaseResult]]
SummarizeResults = Callable[[list[dict[str, Any]]], Mapping[str, Any]]
CheckpointWriter = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class ShardSpec:
    """集中校验分片边界，避免不同评测 CLI 对非法索引产生不同解释。"""

    index: int
    count: int

    def __post_init__(self) -> None:
        # bool 是 int 的子类，但把 true 当作分片编号会让 CLI/JSON 契约产生歧义。
        if type(self.index) is not int or type(self.count) is not int:
            raise ValueError("分片索引和分片总数必须是整数")
        if self.count <= 0:
            raise ValueError("分片总数必须大于 0")
        if self.index < 0 or self.index >= self.count:
            raise ValueError("分片索引必须位于 [0, shard_count) 范围内")


class AtomicCheckpointWriter:
    """先落临时文件再原子替换，确保取消进程时旧 checkpoint 仍可解析。"""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def write(self, payload: Mapping[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.output_path.name}.",
            suffix=".tmp",
            dir=self.output_path.parent,
        )
        temporary_path = Path(temporary_name)

        try:
            # Windows 不允许保留 mkstemp 句柄后再次打开同一路径，先关闭独占创建句柄。
            os.close(descriptor)
            descriptor = -1
            # flush + fsync 保证替换前内容已经交给操作系统，不能暴露半写 JSON。
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(self.output_path)
        except BaseException:
            # 包括任务取消在内的失败都只清理临时文件，绝不删除上一版有效证据。
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                # 清理失败不能遮蔽真正的写入/替换错误，残留临时文件也不会被汇总器消费。
                pass
            raise


def case_file_sha256(case_file: str | Path) -> str:
    """对原始 case pack 字节做哈希，防止相同文件名掩盖评测口径变化。"""
    return hashlib.sha256(Path(case_file).read_bytes()).hexdigest()


def select_shard_cases(cases: Sequence[Case], shard: ShardSpec) -> list[Case]:
    """按原始位置 round-robin 分片，兼顾稳定性和慢 case 分散。"""
    return [case for position, case in enumerate(cases) if position % shard.count == shard.index]


def _validated_case_ids(cases: Sequence[Case]) -> list[str]:
    """在任何 LLM 调用前拒绝无 ID 或重复 ID，保证后续证据可以唯一合并。"""
    case_ids: list[str] = []
    seen: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("每条评测 case 必须提供非空字符串 case ID")
        if case_id in seen:
            raise ValueError(f"评测 case ID 重复: {case_id}")
        seen.add(case_id)
        case_ids.append(case_id)
    return case_ids


def _build_checkpoint(
    *,
    suite: str,
    shard: ShardSpec,
    case_hash: str,
    expected_case_ids: list[str],
    results: list[dict[str, Any]],
    summarize: SummarizeResults,
    head_sha: str,
    provider: str,
    model: str,
) -> dict[str, Any]:
    completed_case_ids = [str(result["case_id"]) for result in results]
    return {
        "shard": {
            "schema_version": 1,
            "suite": suite,
            "head_sha": head_sha,
            "provider": provider,
            "model": model,
            "case_file_sha256": case_hash,
            "shard_index": shard.index,
            "shard_count": shard.count,
            "expected_case_ids": expected_case_ids,
            "completed_case_ids": completed_case_ids,
            "complete": len(completed_case_ids) == len(expected_case_ids),
        },
        "summary": dict(summarize(results)),
        "results": list(results),
    }


async def run_evaluation_shard(
    *,
    cases: Sequence[Case],
    evaluate_case: EvaluateCase,
    summarize: SummarizeResults,
    shard: ShardSpec,
    suite: str,
    case_file: str | Path,
    checkpoint_writer: CheckpointWriter,
    head_sha: str,
    provider: str,
    model: str,
    inter_case_delay_seconds: float = 0,
) -> dict[str, Any]:
    """顺序运行一个分片，并在每条 case 后保存可恢复证据。"""
    all_case_ids = _validated_case_ids(cases)
    selected_cases = select_shard_cases(cases, shard)
    expected_case_ids = [
        all_case_ids[position]
        for position in range(len(cases))
        if position % shard.count == shard.index
    ]
    case_hash = case_file_sha256(case_file)
    results: list[dict[str, Any]] = []

    def checkpoint() -> dict[str, Any]:
        payload = _build_checkpoint(
            suite=suite,
            shard=shard,
            case_hash=case_hash,
            expected_case_ids=expected_case_ids,
            results=results,
            summarize=summarize,
            head_sha=head_sha,
            provider=provider,
            model=model,
        )
        checkpoint_writer(payload)
        return payload

    # 第一个模型请求也可能挂起，所以先写空 checkpoint，让 artifact 至少能证明分片身份。
    final_report = checkpoint()
    for position, case in enumerate(selected_cases):
        result = await evaluate_case(case)
        if not isinstance(result, Mapping):
            raise ValueError("评测结果必须是字典")
        result_payload = dict(result)
        expected_case_id = expected_case_ids[position]
        if result_payload.get("case_id") != expected_case_id:
            raise ValueError("评测结果 case_id 与当前输入不一致")
        results.append(result_payload)
        final_report = checkpoint()

        # 只在当前分片的相邻请求之间退避，最后一条后不额外占用 job 时间。
        if inter_case_delay_seconds > 0 and position < len(selected_cases) - 1:
            await asyncio.sleep(inter_case_delay_seconds)

    return final_report
