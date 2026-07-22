from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def load_workflow(name):
    path = WORKFLOW_DIR / name
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def workflow_triggers(workflow):
    # PyYAML 1.1 会把无引号的 on 解析为布尔值 True。
    return workflow.get("on", workflow.get(True, {}))


def workflow_commands(workflow):
    return "\n".join(
        str(step.get("run", ""))
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    )


def test_base_ci_has_deterministic_pull_request_checks():
    path, workflow = load_workflow("ci.yml")
    raw = path.read_text(encoding="utf-8")
    triggers = workflow_triggers(workflow)
    commands = workflow_commands(workflow)

    assert "pull_request" in triggers
    assert "push" in triggers
    assert workflow["permissions"]["contents"] == "read"
    assert set(workflow["jobs"]) == {
        "backend-tests",
        "backend-tests-pg",
        "dependency-audit",
        "docker-image-builds",
        "frontend-build",
        "frontend-e2e",
        "secret-scan",
    }
    assert "pytest backend/tests -q" in commands
    assert "python -m ruff check" in commands
    # 沙箱测试会切换子进程 cwd；显式覆盖率配置路径，避免主/子进程混用 branch 与 statement 数据。
    assert "--cov-config=pyproject.toml" in commands
    assert "--cov-branch" in commands
    assert "--cov-fail-under=75" in commands
    assert "python -m alembic -c backend/alembic.ini upgrade head" in commands
    assert "python -m alembic -c backend/alembic.ini downgrade base" in commands
    assert "python -m evaluation.intent_evaluator" in commands
    assert "python -m evaluation.intent_grounding_evaluator" in commands
    assert "python -m evaluation.permission_evaluator --json" in commands
    assert "npm ci" in commands
    assert "npm run test --prefix frontend" in commands
    assert "npm run lint --prefix frontend" in commands
    assert "npm run test:e2e --prefix frontend" in commands
    assert "npm run build" in commands
    assert "git ls-files -z" in commands
    assert "python -m pip_audit -r backend/requirements.txt --strict" in commands
    assert "npm audit --prefix frontend --audit-level=high" in commands
    assert "python -m evaluation.evaluator" not in commands
    assert "MIMO_API_KEY" not in raw
    assert "secrets.QWEN_API_KEY" not in raw
    # 基础 CI 只跑确定性检查；真实模型评测由手动 workflow 承担。
    assert "pull_request_target" not in raw


def test_base_ci_builds_docker_images_from_compose_contexts():
    path, workflow = load_workflow("ci.yml")
    raw = path.read_text(encoding="utf-8")
    job = workflow["jobs"]["docker-image-builds"]
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])

    assert job["name"] == "Docker image builds"
    assert job["runs-on"] == "ubuntu-latest"
    assert any(step.get("uses") == "actions/checkout@v6" for step in job["steps"])
    # 这里锁定 docker-compose.yml 中的真实 build context，避免镜像构建链路只停留在文档承诺。
    assert "docker build -f backend/Dockerfile -t data-analyst-agent-backend:ci ." in commands
    assert (
        "docker build -f frontend/Dockerfile -t data-analyst-agent-frontend:ci ./frontend"
        in commands
    )
    assert "backend/Dockerfile" in raw
    assert "frontend/Dockerfile" in raw


def test_base_ci_validates_docker_compose_configuration():
    _, workflow = load_workflow("ci.yml")
    job = workflow["jobs"]["docker-image-builds"]
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    step_names = [step.get("name") for step in steps]

    assert "Validate Docker Compose configuration" in step_names
    assert "docker compose -f docker-compose.yml config" in commands
    assert "docker compose -f docker-compose.yml -f docker-compose.secure.yml config" in commands
    assert commands.index("docker compose -f docker-compose.yml config") < commands.index(
        "docker build -f backend/Dockerfile"
    )


def test_base_ci_smoke_tests_backend_container_readiness():
    _, workflow = load_workflow("ci.yml")
    job = workflow["jobs"]["docker-image-builds"]
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    smoke_step = next(
        step for step in steps if step.get("name") == "Smoke test backend container readiness"
    )
    cleanup_step = next(
        step for step in steps if step.get("name") == "Stop Docker Compose services"
    )

    assert smoke_step["env"]["QWEN_API_KEY"] == "replace-me"
    assert smoke_step["env"]["QWEN_API_URL"] == "http://127.0.0.1:9/v1/chat/completions"
    assert smoke_step["env"]["QWEN_MODEL"] == "mimo-v2.5-pro"
    assert "docker compose -f docker-compose.yml up -d backend" in smoke_step["run"]
    assert "for attempt in {1..60}" in smoke_step["run"]
    assert "curl --fail --silent http://localhost:8000/health/readiness" in smoke_step["run"]
    assert "docker compose -f docker-compose.yml logs backend" in smoke_step["run"]
    assert cleanup_step["if"] == "always()"
    assert cleanup_step["run"] == "docker compose -f docker-compose.yml down -v"
    assert commands.index("docker build -f frontend/Dockerfile") < commands.index(
        "docker compose -f docker-compose.yml up -d backend"
    )


def test_base_ci_runs_frontend_unit_tests_before_build():
    _, workflow = load_workflow("ci.yml")
    job = workflow["jobs"]["frontend-build"]
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    step_names = [step.get("name") for step in job["steps"]]

    assert job["name"] == "Frontend production build"
    assert "Run frontend unit tests" in step_names
    assert "Run frontend lint" in step_names
    assert "npm run test --prefix frontend" in commands
    assert commands.index("npm run test --prefix frontend") < commands.index(
        "npm run build --prefix frontend"
    )
    assert commands.index("npm run lint --prefix frontend") < commands.index(
        "npm run build --prefix frontend"
    )


def test_base_ci_runs_frontend_e2e_tests_with_playwright_chromium():
    _, workflow = load_workflow("ci.yml")
    job = workflow["jobs"]["frontend-e2e"]
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    step_names = [step.get("name") for step in steps]

    assert job["name"] == "Frontend E2E tests"
    assert job["runs-on"] == "ubuntu-latest"
    assert any(step.get("uses") == "actions/checkout@v6" for step in steps)
    assert any(step.get("uses") == "actions/setup-python@v6" for step in steps)
    assert any(step.get("uses") == "actions/setup-node@v6" for step in steps)
    assert "Install backend dependencies" in step_names
    assert "Install frontend dependencies" in step_names
    assert "Install Playwright Chromium" in step_names
    assert "Run frontend E2E tests" in step_names
    assert "pip install -r backend/requirements.txt" in commands
    assert "npm ci --prefix frontend" in commands
    assert "npm exec --prefix frontend playwright install --with-deps chromium" in commands
    assert "npm run test:e2e --prefix frontend" in commands
    assert commands.index("pip install -r backend/requirements.txt") < commands.index(
        "npm run test:e2e --prefix frontend"
    )
    assert commands.index("npm ci --prefix frontend") < commands.index(
        "npm exec --prefix frontend playwright install --with-deps chromium"
    )
    assert commands.index(
        "npm exec --prefix frontend playwright install --with-deps chromium"
    ) < commands.index("npm run test:e2e --prefix frontend")


def test_real_llm_workflow_declares_provider_identity_smoke_and_auditable_artifact():
    path, workflow = load_workflow("real-qwen-evaluation.yml")
    raw = path.read_text(encoding="utf-8")
    triggers = workflow_triggers(workflow)
    commands = workflow_commands(workflow)
    jobs = workflow["jobs"]

    assert set(triggers) == {"workflow_dispatch"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert {"llm_provider", "api_url", "model", "enforce_thresholds"} <= set(inputs)
    assert inputs["llm_provider"]["options"] == ["mimo", "qwen"]
    assert inputs["model"]["default"] == "mimo-v2.5-pro"
    assert inputs["api_url"]["default"].startswith("https://token-plan-cn.xiaomimimo.com/")
    assert workflow["permissions"]["contents"] == "read"
    assert set(jobs) == {
        "preflight",
        "nl2sql-shards",
        "repair-shards",
        "correctness-shards",
        "quality-gate",
    }
    assert "secrets.QWEN_API_KEY" in raw
    assert "secrets.MIMO_API_KEY" in raw
    assert "secrets.DASHSCOPE_API_KEY" in raw
    assert "pull_request_target" not in raw

    preflight = jobs["preflight"]
    assert preflight["timeout-minutes"] == 60
    assert preflight["env"]["EVALUATION_HEAD_SHA"] == "${{ github.sha }}"
    assert "pytest backend/tests -q" in commands
    assert "python -m evaluation.run_metadata" in commands
    assert "python -m evaluation.real_model_smoke" in commands
    assert "python -m evaluation.intent_evaluator" in commands
    assert "run-metadata.json" in raw
    assert "real-model-smoke.json" in raw

    matrix_contracts = {
        "nl2sql-shards": (list(range(13)), "python -m evaluation.evaluator", 13),
        "repair-shards": (list(range(3)), "python -m evaluation.repair_evaluator", 3),
        "correctness-shards": (
            list(range(5)),
            "python -m evaluation.result_correctness_evaluator",
            5,
        ),
    }
    for job_name, (indices, command, shard_count) in matrix_contracts.items():
        job = jobs[job_name]
        assert job["strategy"]["fail-fast"] is False
        assert job["strategy"]["max-parallel"] == 2
        assert job["strategy"]["matrix"]["shard_index"] == indices
        assert job["timeout-minutes"] == 90
        assert job["env"]["EVALUATION_HEAD_SHA"] == "${{ github.sha }}"
        assert job["env"]["LLM_PROVIDER"] == "${{ inputs.llm_provider }}"
        assert job["env"]["QWEN_MODEL"] == "${{ inputs.model }}"
        run_step = next(step for step in job["steps"] if command in str(step.get("run", "")))
        assert run_step["timeout-minutes"] == 75
        assert f"--shard-count {shard_count}" in str(run_step["run"])
        assert "--shard-index ${{ matrix.shard_index }}" in str(run_step["run"])
        assert "--checkpoint-output" in str(run_step["run"])
        upload = next(
            step
            for step in job["steps"]
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        )
        assert upload["if"] == "always()"
        assert "${{ github.run_id }}" in upload["with"]["name"]
        assert "${{ matrix.shard_index }}" in upload["with"]["name"]

    assert jobs["nl2sql-shards"]["needs"] == "preflight"
    assert jobs["repair-shards"]["needs"] == ["preflight", "nl2sql-shards"]
    assert "always()" in jobs["repair-shards"]["if"]
    assert "needs.preflight.result == 'success'" in jobs["repair-shards"]["if"]
    assert jobs["correctness-shards"]["needs"] == ["preflight", "repair-shards"]
    assert "always()" in jobs["correctness-shards"]["if"]

    quality_job = jobs["quality-gate"]
    assert quality_job["if"] == "${{ always() }}"
    assert "EVALUATION_REPORT_DIR" not in quality_job.get("env", {})
    assert set(quality_job["needs"]) == {
        "preflight",
        "nl2sql-shards",
        "repair-shards",
        "correctness-shards",
    }
    download_steps = [
        step
        for step in quality_job["steps"]
        if str(step.get("uses", "")).startswith("actions/download-artifact@")
    ]
    assert len(download_steps) == 4
    assert all(step["uses"] == "actions/download-artifact@v8" for step in download_steps)
    assert all(step.get("continue-on-error") is True for step in download_steps)
    assert {step["with"].get("merge-multiple") for step in download_steps} == {True}
    assert "real-llm-nl2sql-${{ github.run_id }}-shard-*" in raw
    assert "real-llm-repair-${{ github.run_id }}-shard-*" in raw
    assert "real-llm-correctness-${{ github.run_id }}-shard-*" in raw

    assert commands.count("python -m evaluation.shard_report_aggregator") == 3
    assert "--expected-head-sha \"${{ github.sha }}\"" in commands
    assert "--expected-provider \"${{ inputs.llm_provider }}\"" in commands
    assert "--expected-model \"${{ inputs.model }}\"" in commands
    assert "python -m evaluation.intent_grounding_evaluator" in commands
    assert "python -m evaluation.permission_evaluator --write-report" in commands
    assert "python -m evaluation.quality_gate" in commands
    assert "python -m evaluation.security_audit_exporter" in commands
    assert "--correctness-report" in commands
    assert "--intent-grounding-report" in commands
    assert "--permission-report" in commands
    assert "--quality-gate-report" in commands
    assert "--fail-on-missing-real-reports" in commands
    assert "AUDIT_ARGS=()" in commands
    assert 'if [[ -n "$NL2SQL_REPORT" ]]' in commands
    assert 'if [[ -f "$QUALITY_GATE_REPORT" ]]' in commands
    assert '"${AUDIT_ARGS[@]}"' in commands
    assert "$EVALUATION_REPORT_DIR/quality-gate.json" in commands

    report_steps = [
        step
        for step in quality_job["steps"]
        if "$EVALUATION_REPORT_DIR" in str(step.get("run", ""))
    ]
    assert report_steps
    assert all(
        step.get("env", {}).get("EVALUATION_REPORT_DIR")
        == "${{ runner.temp }}/llm-evaluation"
        for step in report_steps
    )

    audit_step = next(
        step
        for step in quality_job["steps"]
        if "python -m evaluation.security_audit_exporter" in str(step.get("run", ""))
    )
    assert audit_step["if"] == "always()"
    final_upload = next(
        step
        for step in quality_job["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    )
    assert final_upload["if"] == "always()"
    assert final_upload["with"]["name"] == "real-llm-quality-gate-${{ github.run_id }}"
    assert "actions/upload-artifact@v7" in raw
    assert "QWEN_API_KEY" not in quality_job.get("env", {})

    assert "python -m evaluation.evaluator" in commands
    assert "python -m evaluation.repair_evaluator" in commands
    assert "python -m evaluation.result_correctness_evaluator" in commands
    assert "python -m scripts.prepare_evaluation_database" in commands
    assert "$GITHUB_STEP_SUMMARY" in commands
