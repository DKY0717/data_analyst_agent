"""真实模型评测分片基础组件测试。"""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from evaluation.shard_support import (
    AtomicCheckpointWriter,
    ShardSpec,
    case_file_sha256,
    run_evaluation_shard,
    select_shard_cases,
)


def make_cases(count: int) -> list[dict[str, str]]:
    """构造稳定 case ID，便于直接观察 round-robin 分片结果。"""
    return [{"id": f"case-{index}", "question": f"问题 {index}"} for index in range(count)]


@pytest.mark.parametrize(
    ("shard_index", "shard_count"),
    [(-1, 2), (0, 0), (2, 2), (True, 2), (0, False)],
)
def test_shard_spec_rejects_invalid_bounds(shard_index, shard_count):
    with pytest.raises(ValueError):
        ShardSpec(index=shard_index, count=shard_count)


def test_round_robin_shards_are_stable_and_cover_every_case_once():
    cases = make_cases(8)

    shards = [
        select_shard_cases(cases, ShardSpec(index=index, count=3))
        for index in range(3)
    ]

    assert [[case["id"] for case in shard] for shard in shards] == [
        ["case-0", "case-3", "case-6"],
        ["case-1", "case-4", "case-7"],
        ["case-2", "case-5"],
    ]
    assert sorted(case["id"] for shard in shards for case in shard) == [
        case["id"] for case in cases
    ]


def test_case_file_sha256_hashes_raw_case_pack_bytes(tmp_path):
    case_file = tmp_path / "cases.yaml"
    content = "cases:\n  - id: case-0\n"
    # 直接写 bytes，避免 Windows 文本换行转换改变“原始文件字节”的测试口径。
    case_file.write_bytes(content.encode("utf-8"))

    assert case_file_sha256(case_file) == hashlib.sha256(content.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_run_evaluation_shard_checkpoints_initial_and_each_completed_case(tmp_path):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text("cases: []\n", encoding="utf-8")
    snapshots = []

    async def evaluate_case(case):
        return {"case_id": case["id"], "passed": True}

    def summarize(results):
        return {"total_cases": len(results), "pass_rate": len(results) / 2}

    def record_checkpoint(payload):
        # 深拷贝证明后续 append 不会回写已经落盘的历史 checkpoint。
        snapshots.append(deepcopy(payload))

    report = await run_evaluation_shard(
        cases=make_cases(4),
        evaluate_case=evaluate_case,
        summarize=summarize,
        shard=ShardSpec(index=0, count=2),
        suite="nl2sql",
        case_file=case_file,
        checkpoint_writer=record_checkpoint,
        head_sha="abc123",
        provider="mimo",
        model="mimo-v2.5-pro",
    )

    assert [snapshot["shard"]["complete"] for snapshot in snapshots] == [False, False, True]
    assert [snapshot["shard"]["completed_case_ids"] for snapshot in snapshots] == [
        [],
        ["case-0"],
        ["case-0", "case-2"],
    ]
    assert snapshots[0]["shard"]["expected_case_ids"] == ["case-0", "case-2"]
    assert snapshots[0]["shard"]["case_file_sha256"] == case_file_sha256(case_file)
    assert snapshots[0]["shard"]["head_sha"] == "abc123"
    assert snapshots[0]["shard"]["provider"] == "mimo"
    assert snapshots[0]["shard"]["model"] == "mimo-v2.5-pro"
    assert report == snapshots[-1]
    assert report["summary"] == {"total_cases": 2, "pass_rate": 1.0}


@pytest.mark.asyncio
async def test_empty_shard_immediately_writes_complete_checkpoint(tmp_path):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text("cases: []\n", encoding="utf-8")
    snapshots = []

    async def should_not_run(_case):
        raise AssertionError("空分片不应执行 case")

    report = await run_evaluation_shard(
        cases=make_cases(1),
        evaluate_case=should_not_run,
        summarize=lambda results: {"total_cases": len(results)},
        shard=ShardSpec(index=2, count=3),
        suite="repair",
        case_file=case_file,
        checkpoint_writer=lambda payload: snapshots.append(deepcopy(payload)),
        head_sha="abc123",
        provider="mimo",
        model="mimo-v2.5-pro",
    )

    assert len(snapshots) == 1
    assert report["shard"]["complete"] is True
    assert report["results"] == []


def test_atomic_checkpoint_failure_preserves_previous_valid_json(monkeypatch, tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text('{"version": "old"}\n', encoding="utf-8")
    writer = AtomicCheckpointWriter(checkpoint)

    def fail_replace(_self, _target):
        raise OSError("simulated replace failure")

    # 替换失败模拟进程取消前的最后窗口；旧 checkpoint 必须仍是完整 JSON。
    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        writer.write({"version": "new"})

    assert json.loads(checkpoint.read_text(encoding="utf-8")) == {"version": "old"}
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_shard_runner_rejects_duplicate_or_missing_case_ids(tmp_path):
    case_file = tmp_path / "cases.yaml"
    case_file.write_text("cases: []\n", encoding="utf-8")

    async def evaluate_case(case):
        return {"case_id": case.get("id")}

    async def run(cases):
        return await run_evaluation_shard(
            cases=cases,
            evaluate_case=evaluate_case,
            summarize=lambda results: {"total_cases": len(results)},
            shard=ShardSpec(index=0, count=1),
            suite="nl2sql",
            case_file=case_file,
            checkpoint_writer=lambda _payload: None,
            head_sha="abc123",
            provider="mimo",
            model="mimo-v2.5-pro",
        )

    # 分开 await 两种失败输入，确保问题在调用模型前就被拒绝。
    with pytest.raises(ValueError, match="重复"):
        await run([{"id": "same"}, {"id": "same"}])
    with pytest.raises(ValueError, match="case ID"):
        await run([{"question": "missing id"}])
