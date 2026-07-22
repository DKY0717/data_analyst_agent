import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "interview_demo_preflight.py"
SPEC = importlib.util.spec_from_file_location("interview_demo_preflight", SCRIPT_PATH)
interview_demo_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(interview_demo_preflight)


def test_evaluate_preflight_reads_demo_env_without_leaking_secret(tmp_path):
    repo_root = tmp_path
    (repo_root / ".env").write_text(
        "JWT_SECRET=super-secret-value-that-is-at-least-32-characters\nAUTH_DEMO_ENABLED=true\n",
        encoding="utf-8",
    )
    for relative_path in interview_demo_preflight.REQUIRED_FILES:
        file_path = repo_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("placeholder", encoding="utf-8")

    result = interview_demo_preflight.evaluate_preflight(
        repo_root=repo_root,
        env={},
        check_network=False,
    )
    markdown = interview_demo_preflight.build_preflight_report(result)

    assert result.failed_count == 0
    assert "JWT_SECRET" in markdown
    assert "AUTH_DEMO_ENABLED=true" in markdown
    assert "super-secret-value-that-is-at-least-32-characters" not in markdown


def test_evaluate_preflight_reports_missing_demo_env_and_core_files(tmp_path):
    result = interview_demo_preflight.evaluate_preflight(
        repo_root=tmp_path,
        env={},
        check_network=False,
    )
    markdown = interview_demo_preflight.build_preflight_report(result)

    assert result.failed_count > 0
    assert "JWT_SECRET 缺失或少于 32 字符" in markdown
    assert "AUTH_DEMO_ENABLED 不是 true" in markdown
    assert "backend/app/main.py" in markdown
    assert "python scripts/interview_demo_preflight.py --strict" in markdown


def test_build_preflight_report_includes_demo_sequence_and_commands(tmp_path):
    for relative_path in interview_demo_preflight.REQUIRED_FILES:
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("placeholder", encoding="utf-8")

    result = interview_demo_preflight.evaluate_preflight(
        repo_root=tmp_path,
        env={"JWT_SECRET": "from-env-secret-that-is-at-least-32", "AUTH_DEMO_ENABLED": "true"},
        check_network=False,
    )
    markdown = interview_demo_preflight.build_preflight_report(result)

    assert "# Data Analyst Agent 面试演示预检" in markdown
    assert "cd backend && uvicorn app.main:app --reload" in markdown
    assert "cd frontend && npm run dev" in markdown
    assert "python -m evaluation.core_path_runner" in markdown
    assert "HEAD SHA" in markdown
    assert "统计 2024 年每个月的销售额" in markdown
    assert "分析各商品类别的退款率" in markdown
    assert "只看订单数，按月份升序排列" in markdown
    assert "列出客户姓名和注册日期" in markdown
    assert "删除订单表" in markdown
    assert "demo:analyst" in markdown
    assert "demo:admin" in markdown
    assert "row_filter_region_scope" in markdown
    assert "block_unauthorized_column" in markdown


def test_preflight_requires_v17_execution_and_deployment_evidence():
    assert "backend/evaluation/core_path_runner.py" in interview_demo_preflight.REQUIRED_FILES
    assert "backend/alembic/versions/20260711_0001_initial_schema.py" in interview_demo_preflight.REQUIRED_FILES
    assert "docker-compose.secure.yml" in interview_demo_preflight.REQUIRED_FILES
    assert ".github/workflows/ci.yml" in interview_demo_preflight.REQUIRED_FILES


def test_network_checks_fail_when_local_services_are_unreachable(tmp_path):
    for relative_path in interview_demo_preflight.REQUIRED_FILES:
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("placeholder", encoding="utf-8")

    result = interview_demo_preflight.evaluate_preflight(
        repo_root=tmp_path,
        env={"JWT_SECRET": "from-env-secret-that-is-at-least-32", "AUTH_DEMO_ENABLED": "true"},
        check_network=True,
        url_checker=lambda _url, _timeout: False,
    )
    markdown = interview_demo_preflight.build_preflight_report(result)

    assert result.failed_count == 2
    assert "后端 readiness 不可访问" in markdown
    assert "前端页面不可访问" in markdown


def test_main_writes_report_and_strict_exit_code(tmp_path):
    output_path = tmp_path / "preflight.md"

    exit_code = interview_demo_preflight.main(
        [
            "--repo-root",
            str(tmp_path),
            "--no-network",
            "--strict",
            "--output",
            str(output_path),
        ],
        env={},
    )

    assert exit_code == 1
    markdown = output_path.read_text(encoding="utf-8")
    assert "面试演示预检" in markdown
    assert "FAIL" in markdown
