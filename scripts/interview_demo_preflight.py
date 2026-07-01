#!/usr/bin/env python3
"""面试前检查本地演示环境是否准备好。"""

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REQUIRED_FILES = (
    "backend/app/main.py",
    "frontend/package.json",
    "database/seed_data.py",
    "scripts/interview_evidence.py",
    "docs/interview_guide.md",
    "docs/resume_project_packet.md",
)

DEMO_SEQUENCE = (
    ("Analyst", "统计 2024 年每个月的销售额", "展示 demo:analyst、row_filter_region_scope 和图表结果"),
    ("Analyst", "列出客户姓名和注册日期", "展示 block_unauthorized_column 与 customers.customer_name"),
    ("Admin", "列出客户姓名和注册日期", "展示 demo:admin 被授权执行同一问题"),
)


@dataclass(frozen=True)
class CheckResult:
    """单条预检结果；message 只写状态，不写任何密钥值。"""

    name: str
    status: str
    message: str


@dataclass(frozen=True)
class PreflightResult:
    """聚合预检结果，方便 CLI 和测试共用同一套判断。"""

    checks: tuple[CheckResult, ...]
    backend_url: str
    frontend_url: str
    network_checked: bool

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status == "FAIL")

    @property
    def warning_count(self) -> int:
        return sum(1 for check in self.checks if check.status == "WARN")


def load_dotenv_values(repo_root: Path) -> dict[str, str]:
    """读取本地 .env 的键值；只返回内存字典，报告层永不输出 secret value。"""
    env_path = repo_root / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merged_demo_env(repo_root: Path, env: dict[str, str]) -> dict[str, str]:
    """环境变量优先于 .env，避免脚本误导当前 shell 实际运行状态。"""
    values = load_dotenv_values(repo_root)
    for key in ("JWT_SECRET", "AUTH_DEMO_ENABLED"):
        if key in env:
            values[key] = env[key]
    return values


def check_url(url: str, timeout_seconds: float) -> bool:
    """用标准库做轻量 localhost 探测，避免为了预检引入额外依赖。"""
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 500
    except (OSError, URLError):
        return False


def evaluate_preflight(
    repo_root: Path,
    env: dict[str, str] | None = None,
    backend_url: str = "http://localhost:8000/health/readiness",
    frontend_url: str = "http://localhost:3000",
    check_network: bool = True,
    timeout_seconds: float = 2.0,
    url_checker: Callable[[str, float], bool] = check_url,
) -> PreflightResult:
    """执行可重复预检；默认检查本地服务，测试可关闭网络探测。"""
    repo_root = repo_root.resolve()
    runtime_env = dict(os.environ if env is None else env)
    demo_env = merged_demo_env(repo_root, runtime_env)
    checks: list[CheckResult] = []

    for relative_path in REQUIRED_FILES:
        status = "PASS" if (repo_root / relative_path).exists() else "FAIL"
        message = "已找到" if status == "PASS" else f"缺少 {relative_path}"
        checks.append(CheckResult(relative_path, status, message))

    jwt_secret = demo_env.get("JWT_SECRET", "")
    checks.append(
        CheckResult(
            "JWT_SECRET",
            "PASS" if jwt_secret else "FAIL",
            "JWT_SECRET 已配置（值已隐藏）" if jwt_secret else "缺少 JWT_SECRET",
        )
    )

    auth_demo_enabled = demo_env.get("AUTH_DEMO_ENABLED", "").lower() == "true"
    checks.append(
        CheckResult(
            "AUTH_DEMO_ENABLED",
            "PASS" if auth_demo_enabled else "FAIL",
            (
                "AUTH_DEMO_ENABLED=true"
                if auth_demo_enabled
                else "AUTH_DEMO_ENABLED 不是 true"
            ),
        )
    )

    if check_network:
        backend_ready = url_checker(backend_url, timeout_seconds)
        checks.append(
            CheckResult(
                "Backend readiness",
                "PASS" if backend_ready else "FAIL",
                f"后端 readiness 可访问: {backend_url}"
                if backend_ready
                else f"后端 readiness 不可访问: {backend_url}",
            )
        )
        frontend_ready = url_checker(frontend_url, timeout_seconds)
        checks.append(
            CheckResult(
                "Frontend dev server",
                "PASS" if frontend_ready else "FAIL",
                f"前端页面可访问: {frontend_url}"
                if frontend_ready
                else f"前端页面不可访问: {frontend_url}",
            )
        )
    else:
        checks.append(CheckResult("Network checks", "WARN", "已跳过本地 URL 探测"))

    return PreflightResult(
        checks=tuple(checks),
        backend_url=backend_url,
        frontend_url=frontend_url,
        network_checked=check_network,
    )


def build_preflight_report(result: PreflightResult) -> str:
    """生成 Markdown 报告，面试前可以直接保存或粘贴到记录里。"""
    lines = [
        "# Data Analyst Agent 面试演示预检",
        "",
        f"- 失败项：{result.failed_count}",
        f"- 警告项：{result.warning_count}",
        f"- 后端检查 URL：`{result.backend_url}`",
        f"- 前端检查 URL：`{result.frontend_url}`",
        "",
        "## 1. 预检结果",
        "",
        "| 检查项 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    for check in result.checks:
        lines.append(f"| {check.name} | {check.status} | {check.message} |")

    lines.extend(
        [
            "",
            "## 2. 启动命令",
            "",
            "```bash",
            "cd backend && uvicorn app.main:app --reload",
            "cd frontend && npm run dev",
            "python scripts/interview_demo_preflight.py --strict",
            "```",
            "",
            "## 3. 演示顺序",
            "",
            "| 身份 | 问题 | 观察点 |",
            "|---|---|---|",
        ]
    )
    for role, question, observation in DEMO_SEQUENCE:
        lines.append(f"| {role} | {question} | {observation} |")

    lines.extend(
        [
            "",
            "## 4. 失败处理",
            "",
            "- 缺少 `JWT_SECRET` 或 `AUTH_DEMO_ENABLED=true`：先补 `.env`，再重启后端。",
            "- 后端 readiness 不可访问：确认 `uvicorn app.main:app --reload` 已在 `backend` 目录启动。",
            "- 前端不可访问：确认 `npm run dev` 已在 `frontend` 目录启动。",
            "",
        ]
    )
    return "\n".join(lines)


def write_stdout(markdown: str) -> None:
    """Windows 控制台编码不稳定，直接写 UTF-8 字节让终端和 Codex 捕获都更可靠。"""
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(markdown.encode("utf-8"))
    else:
        sys.stdout.write(markdown)


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    """CLI 入口；strict 模式遇到 FAIL 返回 1，WARN 不阻断。"""
    parser = argparse.ArgumentParser(description="生成 Data Analyst Agent 面试演示预检报告")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--backend-url", default="http://localhost:8000/health/readiness")
    parser.add_argument("--frontend-url", default="http://localhost:3000")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--no-network", action="store_true", help="跳过本地后端/前端 URL 探测")
    parser.add_argument("--strict", action="store_true", help="存在 FAIL 时返回非零退出码")
    parser.add_argument("--output", type=Path, help="可选 Markdown 输出路径")
    args = parser.parse_args(argv)

    result = evaluate_preflight(
        repo_root=args.repo_root,
        env=env,
        backend_url=args.backend_url,
        frontend_url=args.frontend_url,
        check_network=not args.no_network,
        timeout_seconds=args.timeout,
    )
    markdown = build_preflight_report(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        write_stdout(markdown)

    if args.strict and result.failed_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
