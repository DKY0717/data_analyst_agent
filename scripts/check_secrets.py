#!/usr/bin/env python3
"""扫描已跟踪文本文件中的常见硬编码 Secret。"""

import re
import sys
from pathlib import Path


ALLOW_MARKER = "secret-scan: allow"
PLACEHOLDER_VALUES = {
    "",
    "your_api_key_here",
    "your-api-key-here",
    "replace_me",
    "replace-me",
    "<token>",
    "<secret>",
}

QWEN_API_KEY_PATTERN = re.compile(
    r"\bQWEN_API_KEY\s*[:=]\s*[\"']?([^\"'\s#]+)", re.IGNORECASE
)
BEARER_TOKEN_PATTERN = re.compile(
    r"\bAuthorization\s*:\s*Bearer\s+([A-Za-z0-9._-]{16,})", re.IGNORECASE
)
SK_TOKEN_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return (
        normalized in PLACEHOLDER_VALUES
        or normalized.startswith("${")
        or normalized.startswith("os.getenv(")
    )


def _uses_qwen_environment_variable(line: str) -> bool:
    return (
        'os.getenv("QWEN_API_KEY"' in line
        or "os.getenv('QWEN_API_KEY'" in line
        or "${QWEN_API_KEY}" in line
        or "secrets.QWEN_API_KEY" in line
    )


def scan_text(text: str, path: str) -> list[dict]:
    """返回命中位置和规则名，不保留或返回 Secret 原文。"""
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue

        qwen_match = QWEN_API_KEY_PATTERN.search(line)
        if (
            qwen_match
            and not _uses_qwen_environment_variable(line)
            and not _is_placeholder(qwen_match.group(1))
        ):
            findings.append(
                {
                    "path": path,
                    "line": line_number,
                    "rule": "hardcoded_qwen_api_key",
                }
            )

        if BEARER_TOKEN_PATTERN.search(line):
            findings.append(
                {"path": path, "line": line_number, "rule": "bearer_token"}
            )

        if SK_TOKEN_PATTERN.search(line):
            findings.append({"path": path, "line": line_number, "rule": "sk_token"})

    return findings


def scan_files(paths: list[str]) -> list[dict]:
    """扫描文本文件；二进制文件跳过，读取错误作为门禁命中返回。"""
    findings = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            content = path.read_bytes()
            if b"\x00" in content:
                continue
            text = content.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(
                {
                    "path": raw_path,
                    "line": 0,
                    "rule": f"read_error:{type(exc).__name__}",
                }
            )
            continue

        findings.extend(scan_text(text, raw_path))
    return findings


def main() -> int:
    """从标准输入读取 NUL 分隔路径并执行扫描。"""
    paths = [
        path.decode("utf-8")
        for path in sys.stdin.buffer.read().split(b"\x00")
        if path
    ]
    findings = scan_files(paths)
    for finding in findings:
        print(
            f"{finding['path']}:{finding['line']}: "
            f"secret scan rule {finding['rule']}"
        )

    if findings:
        print(f"Secret scan failed: {len(findings)} finding(s).", file=sys.stderr)
        return 1

    print(f"Secret scan passed: {len(paths)} tracked file(s) checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
