#!/usr/bin/env python3
"""生成面试前可复制的项目证据包命令清单。"""

import argparse
import sys
from pathlib import Path


DEFAULT_ARTIFACT_DIR_TEMPLATE = "artifacts/real-llm-evaluation-{run_id}"


def build_evidence_checklist(
    run_id: str | None = None,
    artifact_dir: str | None = None,
) -> str:
    """返回 Markdown 清单；只生成命令，不联网、不读取 GitHub 登录态。"""
    resolved_run_id = run_id or "<github_run_id>"
    resolved_artifact_dir = artifact_dir or DEFAULT_ARTIFACT_DIR_TEMPLATE.format(
        run_id=resolved_run_id
    )

    # 面试前先拿本地确定性证据，再拿远端真实模型证据，讲述顺序更稳。
    lines = [
        "# Data Analyst Agent 面试证据包",
        "",
        "## 1. 本地确定性证据",
        "",
        "```bash",
        "pytest backend -q",
        "npm run test --prefix frontend",
        "npm run test:e2e --prefix frontend",
        "cd backend && python -m evaluation.security_audit_exporter --write-report",
        "```",
        "",
        "## 2. 远端真实模型评测证据",
        "",
        "```bash",
        "gh run list --workflow real-qwen-evaluation.yml --limit 5",
        f"gh run view {resolved_run_id} --json status,conclusion,url",
        (
            f"gh run download {resolved_run_id} "
            f"--name real-llm-evaluation-{resolved_run_id} "
            f"--dir {resolved_artifact_dir}"
        ),
        "```",
        "",
        "下载后检查 artifact 至少包含：",
        "",
        "- `quality-gate.md/json`",
        "- `security-audit-*.md/json`",
        "- `nl2sql-evaluation-*.md/json`",
        "- `sql-repair-evaluation-*.md/json`",
        "- `result-correctness-evaluation-*.md/json`",
        "- `intent-grounding-evaluation-*.md/json`",
        "- `permission-evaluation-*.md/json`",
        "- `run-metadata.md/json`",
        "- `real-model-smoke.json`",
        "",
        "## 3. 面试展示顺序",
        "",
        "1. 先展示基础 CI 全绿，证明普通 push 不依赖真实 LLM secret。",
        "2. 再展示 Real LLM workflow artifact，核对 provider/model/HEAD 后证明真实模型闭环可复现。",
        "3. 打开 `security-audit-*.md/json`，讲清输入完整性、质量门禁和安全证据矩阵。",
        "4. 最后切到前端权限演示，展示 analyst 行级过滤、越权阻断和 admin 对照。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口；默认写 stdout，可选写入 Markdown 文件。"""
    parser = argparse.ArgumentParser(description="生成 Data Analyst Agent 面试证据包清单")
    parser.add_argument("--run-id", help="真实模型 workflow 的 GitHub Actions run id")
    parser.add_argument("--artifact-dir", help="下载 artifact 的目标目录")
    parser.add_argument("--output", type=Path, help="可选 Markdown 输出路径")
    args = parser.parse_args(argv)

    markdown = build_evidence_checklist(
        run_id=args.run_id,
        artifact_dir=args.artifact_dir,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
